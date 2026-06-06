"""M1 — end-to-end stubbed flow (category J subset).

Walks the full submit → enqueue → worker → comment → status path with a
stubbed LLM. Three tests from the M1 slice of the test plan:

* clean bundle → canned approve verdict lands as ai_reviewer comment;
* AI dark switch → no AI activity, no comment, no stamp;
* simulated restart → orphan scan re-enqueues the unfinished work.

Pytest fixtures and the _make_zip helper are intentionally re-declared
locally so the e2e file reads top-to-bottom and isn't coupled to
test_ai_review_worker.py.
"""
from __future__ import annotations

import io
import time
import zipfile

import pytest

from skills import ai_review, contributions


def _make_zip(name='e2e-test', description='Tiny e2e test skill for M1.'):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            'SKILL.md',
            f'---\nname: {name}\ndescription: {description}\nlicense: MIT\n---\n\n# {name}\n',
        )
    return buf.getvalue()


def _wait_until(predicate, timeout_s=3.0, poll_s=0.02):
    deadline = time.monotonic() + timeout_s
    val = predicate()
    while not val and time.monotonic() < deadline:
        time.sleep(poll_s)
        val = predicate()
    return val


@pytest.fixture
def tmp_contributions(tmp_path):
    """Initialise contributions on a tmp SQLite + blob dir, tear down after."""
    contributions._reset_for_tests()
    ai_review._reset_for_tests()
    db_path = tmp_path / 'submissions.sqlite3'
    blob_dir = tmp_path / 'blobs'
    assert contributions.init_submissions(str(db_path), str(blob_dir)) is True
    yield tmp_path
    ai_review._reset_for_tests()
    contributions._reset_for_tests()


# ── test 1: clean bundle, approve verdict ───────────────────────────────────


def test_e2e_clean_bundle_approve_no_findings(
    tmp_contributions, settings, monkeypatch
):
    """Submit → enqueue → ai_reviewer comment with approve verdict appears."""
    settings.AI_REVIEW_ENABLED = True
    settings.LLM_BASE_URL = 'http://stub'
    settings.LLM_API_KEY = 'k'
    settings.AI_REVIEW_MODELS = ['stub-model']
    settings.AI_REVIEW_PRIVACY_NOTICE = ''

    def fake_call(submission_id, model):
        return ai_review._Verdict(
            overall='approve',
            confidence=0.92,
            summary='Clean bundle. SKILL.md valid, no findings.',
            findings=[],
            model=model,
        )
    monkeypatch.setattr(ai_review, '_call_llm', fake_call)
    assert ai_review.init_reviewer() is True

    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(name='clean-skill'), original_filename='clean.zip',
    )
    ai_review.enqueue_review(sub['id'])

    found = _wait_until(
        lambda: any(
            c['authorRole'] == contributions.ROLE_AI_REVIEWER
            for c in contributions.get_submission(sub['id'])['comments']
        )
    )
    assert found

    full = contributions.get_submission(sub['id'])
    ai_comment = next(
        c for c in full['comments']
        if c['authorRole'] == contributions.ROLE_AI_REVIEWER
    )
    assert 'overall=`approve`' in ai_comment['body']
    assert 'Clean bundle' in ai_comment['body']
    assert full['last_ai_review_ts'] is not None


# ── test 2: dark switch — no AI activity ────────────────────────────────────


def test_e2e_no_ai_action_when_ai_disabled(
    tmp_contributions, settings, monkeypatch
):
    """With AI_REVIEW_ENABLED=false, enqueue is a no-op and nothing happens."""
    settings.AI_REVIEW_ENABLED = False

    # Even if the stub is set up, it must never be called.
    called = []
    monkeypatch.setattr(
        ai_review, '_call_llm',
        lambda sub_id, model: called.append(sub_id) or ai_review._Verdict(
            overall='approve', confidence=1.0, summary='', findings=[], model=model,
        ),
    )
    assert ai_review.init_reviewer() is False

    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(name='dark-skill'), original_filename='dark.zip',
    )
    ai_review.enqueue_review(sub['id'])  # silent no-op

    # Give it generous time — there's no worker to do anything, but we want
    # to be sure no background path triggered.
    time.sleep(0.5)
    full = contributions.get_submission(sub['id'])
    ai_comments = [c for c in full['comments']
                   if c['authorRole'] == contributions.ROLE_AI_REVIEWER]
    assert ai_comments == []
    assert full['last_ai_review_ts'] is None
    assert called == [], '_call_llm must not have been invoked'


# ── test 3: orphan recovery after simulated restart ─────────────────────────


def test_e2e_orphan_recovery_after_simulated_restart(
    tmp_contributions, settings, monkeypatch
):
    """A submission persisted before the reviewer comes up must be reviewed.

    Mimics the deploy / crash recovery story: the previous process left
    work in flight (or never finished it), and the new process's startup
    orphan-scan picks it back up.
    """
    # Create a submission with the reviewer DISABLED (mimicking a previous
    # process that crashed before review).
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(name='orphaned'), original_filename='o.zip',
    )
    assert contributions.get_submission(sub['id'])['last_ai_review_ts'] is None

    # Now "start a new process" — enable the reviewer and init.
    settings.AI_REVIEW_ENABLED = True
    settings.LLM_BASE_URL = 'http://stub'
    settings.LLM_API_KEY = 'k'
    settings.AI_REVIEW_MODELS = ['stub-model']
    settings.AI_REVIEW_PRIVACY_NOTICE = ''

    calls = []
    def fake_call(submission_id, model):
        calls.append(submission_id)
        return ai_review._Verdict(
            overall='approve', confidence=0.9,
            summary='Recovered after restart.', findings=[], model=model,
        )
    monkeypatch.setattr(ai_review, '_call_llm', fake_call)

    assert ai_review.init_reviewer() is True

    found = _wait_until(
        lambda: contributions.get_submission(sub['id'])['last_ai_review_ts'] is not None
    )
    assert found
    assert sub['id'] in calls
    full = contributions.get_submission(sub['id'])
    assert any(
        c['authorRole'] == contributions.ROLE_AI_REVIEWER
        and 'Recovered after restart' in c['body']
        for c in full['comments']
    )
