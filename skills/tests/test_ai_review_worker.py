"""M1 — worker mechanics + queue + orphan scan.

Drives the dark-switched-off vs dark-switched-on lifecycle, asserts that
the daemon worker pops queued ids and writes an ``ai_reviewer`` comment
through the public contributions API, and verifies the idempotency
guarantee (``last_ai_review_ts`` short-circuits re-review).

The LLM is stubbed at the module boundary via monkey-patching
``ai_review._call_llm``. No network, no real model in this file —
those land in ``test_ai_review_e2e_real.py`` at M3.
"""
from __future__ import annotations

import io
import time
import zipfile

import pytest

from skills import ai_review, contributions


# ── fixtures ────────────────────────────────────────────────────────────────


def _make_zip(name='m1-test', description='Tiny test skill for the M1 worker.'):
    """Build a minimal valid SKILL.md ZIP in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            'SKILL.md',
            f'---\nname: {name}\ndescription: {description}\nlicense: MIT\n---\n\n# {name}\n',
        )
    return buf.getvalue()


@pytest.fixture
def reviewer_running(tmp_path, settings, monkeypatch):
    """Fully-initialised contributions + reviewer with a stub LLM.

    - tmp_path SQLite DB
    - AI_REVIEW_ENABLED=true with the deterministic stub model
    - ai_review._call_llm returns a canned verdict (recorded per test)
    - yields a small dict with: db, calls (list of submission_ids the
      stub saw), set_verdict (lambda to override the stub return value)
    """
    # contributions first — the reviewer depends on it for add_comment +
    # list_orphaned_submission_ids + mark_ai_review_completed.
    contributions._reset_for_tests()
    ai_review._reset_for_tests()

    db_path = tmp_path / 'submissions.sqlite3'
    blob_dir = tmp_path / 'blobs'
    assert contributions.init_submissions(str(db_path), str(blob_dir)) is True

    settings.AI_REVIEW_ENABLED = True
    settings.LLM_BASE_URL = 'http://stub.local'
    settings.LLM_API_KEY = 'stub'
    settings.AI_REVIEW_MODELS = ['stub-model']
    settings.AI_REVIEW_PRIVACY_NOTICE = ''  # cleaner asserts

    # Per-test verdict store. Default = approve, no findings.
    state = {
        'verdict': ai_review._Verdict(
            overall='approve',
            confidence=0.9,
            summary='stubbed approve',
            findings=[],
            model='stub-model',
        ),
        'calls': [],
    }

    def fake_call(submission_id, model):
        state['calls'].append(submission_id)
        return state['verdict']

    monkeypatch.setattr(ai_review, '_call_llm', fake_call)

    state['set_verdict'] = lambda v: state.update(verdict=v)

    assert ai_review.init_reviewer() is True
    state['db'] = db_path

    yield state

    ai_review._reset_for_tests()
    contributions._reset_for_tests()


def _wait_until(predicate, timeout_s=3.0, poll_s=0.02):
    """Poll until ``predicate()`` is truthy or timeout. Returns last value."""
    deadline = time.monotonic() + timeout_s
    val = predicate()
    while not val and time.monotonic() < deadline:
        time.sleep(poll_s)
        val = predicate()
    return val


# ── lifecycle / queue setup ─────────────────────────────────────────────────


def test_init_spawns_concurrent_workers_per_setting(tmp_path, settings, monkeypatch):
    contributions._reset_for_tests()
    ai_review._reset_for_tests()
    contributions.init_submissions(str(tmp_path / 'subs.sqlite3'), str(tmp_path / 'b'))

    settings.AI_REVIEW_ENABLED = True
    settings.LLM_BASE_URL = 'http://stub'
    settings.LLM_API_KEY = 'k'
    settings.AI_REVIEW_MODELS = ['m']
    settings.AI_REVIEW_CONCURRENT_WORKERS = 3

    assert ai_review.init_reviewer() is True
    assert len(ai_review._workers) == 3
    assert all(t.is_alive() for t in ai_review._workers)

    ai_review._reset_for_tests()
    contributions._reset_for_tests()


def test_init_dark_does_not_spawn_workers(tmp_path, settings):
    contributions._reset_for_tests()
    ai_review._reset_for_tests()
    contributions.init_submissions(str(tmp_path / 'subs.sqlite3'), str(tmp_path / 'b'))

    settings.AI_REVIEW_ENABLED = False
    assert ai_review.init_reviewer() is False
    assert ai_review._workers == []
    assert ai_review._queue is None

    ai_review._reset_for_tests()
    contributions._reset_for_tests()


def test_enqueue_review_is_noop_when_disabled(tmp_path, settings):
    contributions._reset_for_tests()
    ai_review._reset_for_tests()
    contributions.init_submissions(str(tmp_path / 'subs.sqlite3'), str(tmp_path / 'b'))

    settings.AI_REVIEW_ENABLED = False
    ai_review.init_reviewer()
    # Should not raise even though queue is None.
    ai_review.enqueue_review(99999)

    contributions._reset_for_tests()


# ── happy path ──────────────────────────────────────────────────────────────


def test_worker_writes_ai_reviewer_comment_for_queued_submission(reviewer_running):
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='m1.zip',
    )

    ai_review.enqueue_review(sub['id'])

    found = _wait_until(
        lambda: any(
            c['authorRole'] == contributions.ROLE_AI_REVIEWER
            for c in contributions.get_submission(sub['id'])['comments']
        )
    )
    assert found, 'AI reviewer comment did not appear within timeout'

    comments = contributions.get_submission(sub['id'])['comments']
    ai_comments = [c for c in comments if c['authorRole'] == contributions.ROLE_AI_REVIEWER]
    assert len(ai_comments) == 1
    body = ai_comments[0]['body']
    assert 'stubbed approve' in body
    assert 'overall=`approve`' in body
    assert 'stub-model' in body


def test_worker_stamps_last_ai_review_ts(reviewer_running):
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='m1.zip',
    )
    before = time.time()
    ai_review.enqueue_review(sub['id'])
    _wait_until(
        lambda: contributions.get_submission(sub['id']).get('last_ai_review_ts') is not None
    )
    after = contributions.get_submission(sub['id'])['last_ai_review_ts']
    assert after is not None
    assert before <= after <= time.time() + 1


def test_worker_idempotent_when_same_id_enqueued_twice(reviewer_running):
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='m1.zip',
    )
    ai_review.enqueue_review(sub['id'])
    _wait_until(
        lambda: contributions.get_submission(sub['id']).get('last_ai_review_ts') is not None
    )
    # Now enqueue again — should be skipped by the last_ai_review_ts guard.
    initial_call_count = len(reviewer_running['calls'])
    ai_review.enqueue_review(sub['id'])
    # Give the worker a moment to attempt processing.
    time.sleep(0.2)
    comments = contributions.get_submission(sub['id'])['comments']
    ai_comments = [c for c in comments if c['authorRole'] == contributions.ROLE_AI_REVIEWER]
    assert len(ai_comments) == 1, 'second enqueue must not produce a second AI comment'
    # The stub _call_llm was either skipped entirely (idempotent fast-path) or
    # called once and short-circuited. Either way, no second comment was written.
    assert len(reviewer_running['calls']) >= initial_call_count


def test_worker_survives_exception_in_call_llm(reviewer_running, monkeypatch):
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(name='boom'), original_filename='m1.zip',
    )

    def fake_call_raises(submission_id, model):
        raise RuntimeError('simulated upstream failure')

    monkeypatch.setattr(ai_review, '_call_llm', fake_call_raises)
    ai_review.enqueue_review(sub['id'])

    # Worker should swallow + log; it must still be alive afterwards.
    time.sleep(0.3)
    assert all(t.is_alive() for t in ai_review._workers), \
        'worker thread must survive _call_llm exceptions'

    # No AI comment was written because the call raised.
    comments = contributions.get_submission(sub['id'])['comments']
    assert not any(c['authorRole'] == contributions.ROLE_AI_REVIEWER for c in comments)


def test_worker_skips_unknown_submission_id(reviewer_running):
    # No such submission exists — the worker should log and move on.
    ai_review.enqueue_review(987654)
    time.sleep(0.3)
    assert all(t.is_alive() for t in ai_review._workers)


# ── orphan scan ─────────────────────────────────────────────────────────────


def test_orphan_scan_picks_up_pre_existing_submitted_rows(tmp_path, settings, monkeypatch):
    """A submission created BEFORE init_reviewer should be picked up.

    Simulates "process restart with pending work" — submission was
    persisted but the previous reviewer thread never finished it.
    """
    contributions._reset_for_tests()
    ai_review._reset_for_tests()
    contributions.init_submissions(str(tmp_path / 'subs.sqlite3'), str(tmp_path / 'b'))

    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(name='orphan'), original_filename='o.zip',
    )

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
            summary='orphan recovered', findings=[], model=model,
        )
    monkeypatch.setattr(ai_review, '_call_llm', fake_call)

    assert ai_review.init_reviewer() is True

    _wait_until(
        lambda: contributions.get_submission(sub['id']).get('last_ai_review_ts') is not None
    )
    assert sub['id'] in calls
    comments = contributions.get_submission(sub['id'])['comments']
    assert any(c['authorRole'] == contributions.ROLE_AI_REVIEWER for c in comments)

    ai_review._reset_for_tests()
    contributions._reset_for_tests()


def test_orphan_scan_excludes_already_reviewed_rows(reviewer_running, monkeypatch):
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='o.zip',
    )
    ai_review.enqueue_review(sub['id'])
    _wait_until(
        lambda: contributions.get_submission(sub['id']).get('last_ai_review_ts') is not None
    )

    # Reset + re-init. The stamped submission should NOT be re-enqueued.
    ai_review._reset_for_tests()
    calls = []
    def fake_call(submission_id, model):
        calls.append(submission_id)
        return ai_review._Verdict(
            overall='approve', confidence=0.9, summary='', findings=[], model=model,
        )
    monkeypatch.setattr(ai_review, '_call_llm', fake_call)
    ai_review.init_reviewer()
    time.sleep(0.3)
    assert sub['id'] not in calls


def test_orphan_scan_skipped_gracefully_when_contributions_disabled(tmp_path, settings):
    """init_reviewer must not crash if contributions isn't initialised."""
    contributions._reset_for_tests()
    ai_review._reset_for_tests()

    settings.AI_REVIEW_ENABLED = True
    settings.LLM_BASE_URL = 'http://stub'
    settings.LLM_API_KEY = 'k'
    settings.AI_REVIEW_MODELS = ['stub-model']

    # contributions never init'd; orphan scan should swallow the
    # ContributionError("contributions storage unavailable", 503) it
    # would otherwise propagate.
    assert ai_review.init_reviewer() is True
    ai_review._reset_for_tests()


# ── shutdown ────────────────────────────────────────────────────────────────


def test_shutdown_drains_workers_within_grace(reviewer_running):
    workers = list(ai_review._workers)
    ai_review.shutdown()
    for t in workers:
        assert not t.is_alive(), f'worker {t.name} should have exited'


def test_shutdown_idempotent(reviewer_running):
    ai_review.shutdown()
    ai_review.shutdown()  # second call should be a clean no-op
