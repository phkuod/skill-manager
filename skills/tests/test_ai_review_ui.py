"""M4b — AI verdict UI plumbing.

Two concerns:

* ``views._extract_ai_verdict`` — pulls the latest ``ai_reviewer``
  comment out of the timeline, regex-matches the footer line emitted by
  ``ai_review._render_comment_body``, and reports
  ``{overall, confidence, model, findingsCount, createdTs, createdTsIso}``.
* Template rendering — the detail page verdict pill + Re-run button
  gating, and the admin queue AI column. Driven through the real URL
  routes with ``django.test.Client`` and grepped from the rendered HTML.
"""
from __future__ import annotations

import io
import zipfile

import pytest
from django.test import Client

from skills import ai_review, contributions, views


# ── helpers ─────────────────────────────────────────────────────────────────


def _make_zip(name='m4b-test'):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            'SKILL.md',
            f'---\nname: {name}\ndescription: M4b test skill.\nlicense: MIT\n---\n# {name}\n',
        )
    return buf.getvalue()


def _ai_comment_body(overall='approve', model='stub-model', confidence=0.9,
                     findings=None):
    """Render a faithful ai_reviewer comment body via the real renderer.

    Uses ``ai_review._render_comment_body`` so the footer-line format the
    extractor parses stays in lock-step with what the worker actually
    writes. ``_config`` is left at None ⇒ default cap 0.8, no privacy note.
    """
    verdict = ai_review._Verdict(
        overall=overall, confidence=confidence, summary='synthetic verdict',
        findings=findings or [], model=model,
    )
    return ai_review._render_comment_body(verdict)


def _comment(body, *, role=contributions.ROLE_AI_REVIEWER, created_ts=1000.0):
    return {'authorRole': role, 'body': body, 'createdTs': created_ts}


# ── _extract_ai_verdict (pure unit) ─────────────────────────────────────────


def test_extract_returns_none_for_no_comments():
    assert views._extract_ai_verdict([]) is None


def test_extract_returns_none_when_no_ai_role():
    comments = [
        _comment('a human note', role=contributions.ROLE_ADMIN),
        _comment('submitted', role=contributions.ROLE_SYSTEM),
    ]
    assert views._extract_ai_verdict(comments) is None


def test_extract_returns_none_on_malformed_body():
    # ai_reviewer role but no footer line ⇒ regex misses ⇒ None.
    assert views._extract_ai_verdict([_comment('just some prose, no footer')]) is None


def test_extract_parses_clean_body():
    body = _ai_comment_body(overall='approve', model='qwen-72b', confidence=0.65)
    out = views._extract_ai_verdict([_comment(body)])
    assert out is not None
    assert out['overall'] == 'approve'
    assert out['model'] == 'qwen-72b'
    assert out['confidence'] == pytest.approx(0.65)
    assert out['findingsCount'] == 0


def test_extract_picks_latest_when_multiple_ai_comments():
    older = _comment(
        _ai_comment_body(overall='reject', model='old-model', confidence=0.5),
        created_ts=1000.0,
    )
    newer = _comment(
        _ai_comment_body(overall='approve', model='new-model', confidence=0.7),
        created_ts=2000.0,
    )
    # Intentionally out of order — extractor sorts by createdTs desc.
    out = views._extract_ai_verdict([older, newer])
    assert out['model'] == 'new-model'
    assert out['overall'] == 'approve'


def test_extract_counts_severity_bullets():
    findings = [
        {'severity': 'block', 'title': 'hardcoded secret'},
        {'severity': 'warn', 'title': 'broad glob'},
        {'severity': 'note', 'title': 'style nit'},
    ]
    body = _ai_comment_body(overall='request_changes', findings=findings)
    out = views._extract_ai_verdict([_comment(body)])
    assert out['findingsCount'] == 3


def test_extract_handles_capped_confidence_marker():
    # confidence above the 0.8 cap renders "0.80 (capped)"; the regex
    # captures the numeric prefix and must not choke on the suffix.
    body = _ai_comment_body(overall='approve', confidence=0.97)
    assert '(capped)' in body
    out = views._extract_ai_verdict([_comment(body)])
    assert out['confidence'] == pytest.approx(0.80)


# ── template rendering (integration via Client) ─────────────────────────────


@pytest.fixture
def contrib_ready(tmp_path, settings):
    contributions._reset_for_tests()
    contributions.init_submissions(
        str(tmp_path / 'subs.sqlite3'), str(tmp_path / 'blobs'),
    )
    settings.SKILL_REVIEW_ADMINS = {'dev'}
    yield tmp_path
    contributions._reset_for_tests()


def _submission(submitter='alice'):
    return contributions.create_submission(
        submitter=submitter, submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='s.zip',
    )


def _post_ai_comment(sub_id, **kw):
    contributions.add_comment(
        sub_id, author=None, author_role=contributions.ROLE_AI_REVIEWER,
        body=_ai_comment_body(**kw),
    )


def test_detail_page_renders_ai_verdict_pill_when_present(contrib_ready):
    sub = _submission()
    _post_ai_comment(sub['id'], overall='approve', model='qwen-72b')

    client = Client()
    client.cookies['CURRENT_USER_NAME'] = 'dev'
    resp = client.get(f'/contributions/{sub["id"]}/')
    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'ai-verdict approve' in html
    assert 'qwen-72b' in html


def test_detail_page_omits_ai_verdict_when_no_ai_comment(contrib_ready):
    sub = _submission()

    client = Client()
    client.cookies['CURRENT_USER_NAME'] = 'dev'
    resp = client.get(f'/contributions/{sub["id"]}/')
    assert resp.status_code == 200
    # The .ai-verdict-meta class lives in the static <style> block always;
    # assert the conditionally-rendered verdict line itself is absent.
    assert 'AI verdict by' not in resp.content.decode()


def test_detail_page_rerun_button_visible_to_admin(contrib_ready, settings):
    settings.AI_REVIEW_ENABLED = True
    sub = _submission()

    client = Client()
    client.cookies['CURRENT_USER_NAME'] = 'dev'
    resp = client.get(f'/contributions/{sub["id"]}/')
    assert 'id="rerun-ai-btn"' in resp.content.decode()


def test_detail_page_rerun_button_hidden_from_submitter(contrib_ready, settings):
    settings.AI_REVIEW_ENABLED = True
    sub = _submission(submitter='alice')

    client = Client()
    client.cookies['CURRENT_USER_NAME'] = 'alice'   # submitter, not admin
    resp = client.get(f'/contributions/{sub["id"]}/')
    assert resp.status_code == 200
    assert 'id="rerun-ai-btn"' not in resp.content.decode()


def test_detail_page_rerun_button_disabled_at_quota(contrib_ready, settings):
    settings.AI_REVIEW_ENABLED = True
    settings.AI_REVIEW_RERUN_DAILY_CAP_PER_SUBMISSION = 2
    sub = _submission()
    for _ in range(2):
        contributions.add_comment(
            sub['id'], author='dev', author_role=contributions.ROLE_SYSTEM,
            body=f'{contributions.AI_RERUN_MARKER} by dev',
        )

    client = Client()
    client.cookies['CURRENT_USER_NAME'] = 'dev'
    resp = client.get(f'/contributions/{sub["id"]}/')
    html = resp.content.decode()
    assert 'id="rerun-ai-btn"' in html
    assert 'disabled' in html


def test_detail_page_rerun_button_hidden_when_ai_disabled(contrib_ready, settings):
    settings.AI_REVIEW_ENABLED = False
    sub = _submission()

    client = Client()
    client.cookies['CURRENT_USER_NAME'] = 'dev'
    resp = client.get(f'/contributions/{sub["id"]}/')
    assert 'id="rerun-ai-btn"' not in resp.content.decode()


def test_admin_queue_renders_ai_column_with_verdict_pill(contrib_ready):
    sub = _submission()
    _post_ai_comment(sub['id'], overall='reject', model='deepseek-r1')

    client = Client()
    client.cookies['CURRENT_USER_NAME'] = 'dev'
    resp = client.get('/admin/contributions/')
    assert resp.status_code == 200
    html = resp.content.decode()
    assert '<th>AI</th>' in html
    assert 'ai-verdict reject' in html


def test_admin_queue_uses_latest_ai_comment(contrib_ready):
    sub = _submission()
    _post_ai_comment(sub['id'], overall='reject', model='old')
    _post_ai_comment(sub['id'], overall='approve', model='new')

    client = Client()
    client.cookies['CURRENT_USER_NAME'] = 'dev'
    resp = client.get('/admin/contributions/')
    html = resp.content.decode()
    assert 'ai-verdict approve' in html
    assert 'ai-verdict reject' not in html
