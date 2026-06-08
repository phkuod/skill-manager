"""M4a — auto-status-nudge + admin Re-run AI review endpoint.

Two concerns in one file:

* ``_should_nudge_to_under_review`` + ``_run_review``'s end-of-pipeline
  nudge step: 'always' / 'if_findings' / 'off' policies; only touches
  submitted-status rows; never touches terminal statuses.
* ``api_contribution_rerun_ai`` endpoint: admin-only, quota
  enforcement via ``count_recent_ai_reruns``, clears the
  ``last_ai_review_ts`` stamp, enqueues a fresh review, writes the
  ``AI_RERUN_MARKER`` audit comment.
"""
from __future__ import annotations

import io
import time
import zipfile

import pytest
from django.test import Client

from skills import ai_review, contributions


# ── helpers ─────────────────────────────────────────────────────────────────


def _make_zip(name='m4a-test'):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            'SKILL.md',
            f'---\nname: {name}\ndescription: M4a test skill.\nlicense: MIT\n---\n# {name}\n',
        )
    return buf.getvalue()


def _wait_until(predicate, timeout_s=3.0, poll_s=0.02):
    deadline = time.monotonic() + timeout_s
    val = predicate()
    while not val and time.monotonic() < deadline:
        time.sleep(poll_s)
        val = predicate()
    return val


# ── _should_nudge_to_under_review (pure policy unit) ────────────────────────


def _cfg(nudge_policy='always'):
    return ai_review._Config(
        base_url='http://stub', api_key='k', extra_headers={},
        models=['m'], max_input_tokens=12000, timeout_s=10,
        rate_budget_per_min=15, concurrent_workers=1,
        auto_nudge=nudge_policy,
        confidence_cap=0.8, drop_hallucinated_evidence=False,
        privacy_notice='', rerun_daily_cap=3, catalog_detail='hashes',
    )


def _verdict(findings=None):
    return ai_review._Verdict(
        overall='approve', confidence=0.9, summary='ok',
        findings=findings or [], model='m',
    )


def test_nudge_policy_always_nudges_clean_verdict(monkeypatch):
    monkeypatch.setattr(ai_review, '_config', _cfg('always'))
    assert ai_review._should_nudge_to_under_review(_verdict(), 'submitted') is True


def test_nudge_policy_always_nudges_with_findings(monkeypatch):
    monkeypatch.setattr(ai_review, '_config', _cfg('always'))
    v = _verdict(findings=[{'severity': 'warn', 'category': 'security'}])
    assert ai_review._should_nudge_to_under_review(v, 'submitted') is True


def test_nudge_policy_if_findings_skips_clean_approve(monkeypatch):
    monkeypatch.setattr(ai_review, '_config', _cfg('if_findings'))
    assert ai_review._should_nudge_to_under_review(_verdict(), 'submitted') is False


def test_nudge_policy_if_findings_skips_only_notes(monkeypatch):
    """Note-severity findings don't trip the nudge under 'if_findings'."""
    monkeypatch.setattr(ai_review, '_config', _cfg('if_findings'))
    v = _verdict(findings=[{'severity': 'note', 'category': 'quality'}])
    assert ai_review._should_nudge_to_under_review(v, 'submitted') is False


def test_nudge_policy_if_findings_fires_on_warn(monkeypatch):
    monkeypatch.setattr(ai_review, '_config', _cfg('if_findings'))
    v = _verdict(findings=[{'severity': 'warn', 'category': 'content'}])
    assert ai_review._should_nudge_to_under_review(v, 'submitted') is True


def test_nudge_policy_if_findings_fires_on_block(monkeypatch):
    monkeypatch.setattr(ai_review, '_config', _cfg('if_findings'))
    v = _verdict(findings=[{'severity': 'block', 'category': 'security'}])
    assert ai_review._should_nudge_to_under_review(v, 'submitted') is True


def test_nudge_policy_off_never_nudges(monkeypatch):
    monkeypatch.setattr(ai_review, '_config', _cfg('off'))
    v = _verdict(findings=[{'severity': 'block', 'category': 'security'}])
    assert ai_review._should_nudge_to_under_review(v, 'submitted') is False


@pytest.mark.parametrize('status', [
    'under_review', 'approved', 'changes_requested', 'rejected', 'published',
])
def test_nudge_never_touches_non_submitted(monkeypatch, status):
    monkeypatch.setattr(ai_review, '_config', _cfg('always'))
    assert ai_review._should_nudge_to_under_review(_verdict(), status) is False


# ── _run_review end-to-end with the nudge step ────────────────────────────


@pytest.fixture
def reviewer_running(tmp_path, settings, monkeypatch):
    """Same shape as the M1 worker fixture — drives the full pipeline."""
    contributions._reset_for_tests()
    ai_review._reset_for_tests()
    contributions.init_submissions(
        str(tmp_path / 'subs.sqlite3'), str(tmp_path / 'blobs'),
    )
    settings.AI_REVIEW_ENABLED = True
    settings.LLM_BASE_URL = 'http://stub'
    settings.LLM_API_KEY = 'k'
    settings.AI_REVIEW_MODELS = ['stub-model']
    settings.AI_REVIEW_PRIVACY_NOTICE = ''
    settings.AI_REVIEW_AUTO_NUDGE = 'always'

    state = {
        'verdict': ai_review._Verdict(
            overall='approve', confidence=0.9,
            summary='stub', findings=[], model='stub-model',
        ),
    }

    def fake_call(prompt, model):
        return state['verdict']

    monkeypatch.setattr(ai_review, '_call_llm', fake_call)
    assert ai_review.init_reviewer() is True
    yield state
    ai_review._reset_for_tests()
    contributions._reset_for_tests()


def test_run_review_nudges_submitted_row_under_always(reviewer_running):
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='a.zip',
    )
    assert contributions.get_submission(sub['id'])['status'] == 'submitted'

    ai_review.enqueue_review(sub['id'])
    _wait_until(
        lambda: contributions.get_submission(sub['id'])['status'] == 'under_review'
    )
    assert contributions.get_submission(sub['id'])['status'] == 'under_review'


def test_run_review_respects_off_policy(reviewer_running, settings):
    settings.AI_REVIEW_AUTO_NUDGE = 'off'
    ai_review._config = ai_review._build_config()

    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='b.zip',
    )
    ai_review.enqueue_review(sub['id'])
    # AI comment should land but status stays 'submitted'.
    _wait_until(
        lambda: any(
            c['authorRole'] == contributions.ROLE_AI_REVIEWER
            for c in contributions.get_submission(sub['id'])['comments']
        )
    )
    assert contributions.get_submission(sub['id'])['status'] == 'submitted'


# ── count_recent_ai_reruns helper ────────────────────────────────────────


@pytest.fixture
def contrib_ready(tmp_path):
    contributions._reset_for_tests()
    contributions.init_submissions(
        str(tmp_path / 'subs.sqlite3'), str(tmp_path / 'blobs'),
    )
    yield tmp_path
    contributions._reset_for_tests()


def test_count_recent_zero_when_no_reruns(contrib_ready):
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='c.zip',
    )
    assert contributions.count_recent_ai_reruns(sub['id']) == 0


def test_count_recent_counts_marker_only(contrib_ready):
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='c.zip',
    )
    # 3 rerun system comments + 1 unrelated system comment.
    for _ in range(3):
        contributions.add_comment(
            sub['id'], author='dev', author_role=contributions.ROLE_SYSTEM,
            body=f'{contributions.AI_RERUN_MARKER} by dev',
        )
    contributions.add_comment(
        sub['id'], author=None, author_role=contributions.ROLE_SYSTEM,
        body='some other audit line',
    )
    assert contributions.count_recent_ai_reruns(sub['id']) == 3


def test_count_recent_excludes_old_entries(contrib_ready, monkeypatch):
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='c.zip',
    )
    contributions.add_comment(
        sub['id'], author='dev', author_role=contributions.ROLE_SYSTEM,
        body=f'{contributions.AI_RERUN_MARKER} by dev',
    )
    # Backdate the marker into yesterday by editing the row in-place.
    cutoff = time.time() - 2 * 86400
    with contributions._lock:
        contributions._conn.execute(
            'UPDATE submission_comments SET created_ts = ? '
            'WHERE submission_id = ? AND body LIKE ?',
            (cutoff, sub['id'], f'{contributions.AI_RERUN_MARKER}%'),
        )
    assert contributions.count_recent_ai_reruns(sub['id'], within_seconds=86400) == 0


def test_clear_ai_review_stamp_resets_to_null(contrib_ready):
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='c.zip',
    )
    contributions.mark_ai_review_completed(sub['id'])
    assert contributions.get_submission(sub['id'])['last_ai_review_ts'] is not None
    contributions.clear_ai_review_stamp(sub['id'])
    assert contributions.get_submission(sub['id'])['last_ai_review_ts'] is None


# ── rerun endpoint ────────────────────────────────────────────────────────


@pytest.fixture
def admin_request_setup(contrib_ready, settings, monkeypatch):
    """contributions + admin cookie wired so the rerun endpoint accepts."""
    settings.SKILL_REVIEW_ADMINS = {'dev'}
    settings.AI_REVIEW_ENABLED = False    # no worker; we just want the endpoint
    ai_review._reset_for_tests()
    # Track ai_review.enqueue_review calls without spinning a worker.
    enqueued = []
    monkeypatch.setattr(ai_review, 'enqueue_review',
                        lambda sub_id: enqueued.append(sub_id))
    yield {'enqueued': enqueued}
    ai_review._reset_for_tests()


def _new_submission():
    return contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='r.zip',
    )


def test_rerun_endpoint_403_for_non_admin(admin_request_setup):
    sub = _new_submission()
    client = Client()
    client.cookies['CURRENT_USER_NAME'] = 'eve'   # not in SKILL_REVIEW_ADMINS
    response = client.post(f'/api/contributions/{sub["id"]}/rerun_ai')
    assert response.status_code == 403


def test_rerun_endpoint_404_when_submission_missing(admin_request_setup):
    client = Client()
    client.cookies['CURRENT_USER_NAME'] = 'dev'
    response = client.post('/api/contributions/9999/rerun_ai')
    assert response.status_code == 404


def test_rerun_endpoint_happy_path(admin_request_setup, settings):
    settings.AI_REVIEW_RERUN_DAILY_CAP_PER_SUBMISSION = 3
    sub = _new_submission()
    contributions.mark_ai_review_completed(sub['id'])

    client = Client()
    client.cookies['CURRENT_USER_NAME'] = 'dev'
    response = client.post(f'/api/contributions/{sub["id"]}/rerun_ai')
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok'
    assert body['recentCount'] == 1
    assert body['dailyCap'] == 3

    # Audit comment landed with the marker.
    full = contributions.get_submission(sub['id'])
    rerun_comments = [
        c for c in full['comments']
        if c['authorRole'] == contributions.ROLE_SYSTEM
        and c['body'].startswith(contributions.AI_RERUN_MARKER)
    ]
    assert len(rerun_comments) == 1

    # Stamp cleared so the worker won't short-circuit.
    assert full['last_ai_review_ts'] is None

    # Enqueue happened.
    assert sub['id'] in admin_request_setup['enqueued']


def test_rerun_endpoint_429_after_quota(admin_request_setup, settings):
    settings.AI_REVIEW_RERUN_DAILY_CAP_PER_SUBMISSION = 2
    sub = _new_submission()

    client = Client()
    client.cookies['CURRENT_USER_NAME'] = 'dev'

    # 2 successful requests fill the quota.
    for i in range(2):
        r = client.post(f'/api/contributions/{sub["id"]}/rerun_ai')
        assert r.status_code == 200, (i, r.content)

    # 3rd is denied.
    r = client.post(f'/api/contributions/{sub["id"]}/rerun_ai')
    assert r.status_code == 429
    assert 'quota' in r.json()['error'].lower()
