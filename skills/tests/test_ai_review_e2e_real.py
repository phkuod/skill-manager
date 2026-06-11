"""M3d — opt-in REAL OpenRouter test lane.

These tests hit the live LLM endpoint and are therefore skipped unless
BOTH opt-in conditions hold:

* ``AI_REVIEW_E2E_REAL=1`` in the environment (explicit intent — never
  runs by accident in CI or a default ``pytest`` invocation), and
* an API key in ``LLM_API_KEY`` or ``OPENROUTER_API_KEY``.

Run it like:

    AI_REVIEW_E2E_REAL=1 OPENROUTER_API_KEY=sk-... DEBUG=True \
        pytest skills/tests/test_ai_review_e2e_real.py -q

Design notes:

* Free-tier models rate-limit aggressively. A chain exhausted purely by
  429s is infrastructure noise, not a code bug — those runs ``skip``
  rather than fail.
* A ``parse_failure`` verdict is NOT skipped: the M3 contract says
  unparseable model output must degrade to a structurally valid
  ``needs_human_review`` verdict, so the invariant assertions below
  still apply to it.
* Assertions target OUR contract (verdict structure, rendered comment
  matches the M4b extraction regex), never the model's opinion — the
  same bundle may legitimately get approve or request_changes.
"""
from __future__ import annotations

import io
import os
import time
import zipfile

import pytest

from skills import ai_review, contributions, views

_OPT_IN = os.environ.get('AI_REVIEW_E2E_REAL', '').lower() in ('1', 'true')
_HAS_KEY = bool(
    os.environ.get('LLM_API_KEY') or os.environ.get('OPENROUTER_API_KEY')
)

pytestmark = pytest.mark.skipif(
    not (_OPT_IN and _HAS_KEY),
    reason='real-LLM lane: set AI_REVIEW_E2E_REAL=1 and LLM_API_KEY/OPENROUTER_API_KEY',
)

_VALID_OVERALLS = {'approve', 'request_changes', 'reject', 'needs_human_review'}
# Live calls walk a free-tier fallback chain; budget generously.
_REAL_CALL_TIMEOUT_S = 180.0


def _make_zip(name='real-e2e-skill'):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            'SKILL.md',
            f'---\nname: {name}\n'
            f'description: Summarise a markdown document into bullet points.\n'
            f'license: MIT\n---\n\n# {name}\n\n'
            f'Read the input markdown and produce a 5-bullet summary.\n',
        )
    return buf.getvalue()


def _wait_until(predicate, timeout_s, poll_s=0.25):
    deadline = time.monotonic() + timeout_s
    val = predicate()
    while not val and time.monotonic() < deadline:
        time.sleep(poll_s)
        val = predicate()
    return val


def _assert_verdict_contract(verdict):
    """Structural invariants every returned verdict must satisfy."""
    assert verdict.overall in _VALID_OVERALLS
    assert 0.0 <= verdict.confidence <= 1.0
    assert isinstance(verdict.summary, str) and verdict.summary
    for f in verdict.findings:
        assert f.get('severity') in ('block', 'warn', 'note')
    # The rendered comment must round-trip through the M4b extraction
    # regex — this is the integration seam the UI depends on.
    body = ai_review._render_comment_body(verdict)
    extracted = views._extract_ai_verdict([{
        'authorRole': contributions.ROLE_AI_REVIEWER,
        'body': body,
        'createdTs': 1.0,
    }])
    assert extracted is not None
    assert extracted['overall'] == verdict.overall


@pytest.fixture
def real_reviewer(tmp_path, settings):
    """contributions on tmp storage + reviewer configured from real env.

    settings.LLM_API_KEY / LLM_BASE_URL / AI_REVIEW_MODELS already carry
    the env values via skill_market.settings — only the enable switch
    and storage paths are overridden here.
    """
    contributions._reset_for_tests()
    ai_review._reset_for_tests()
    contributions.init_submissions(
        str(tmp_path / 'subs.sqlite3'), str(tmp_path / 'blobs'),
    )
    settings.AI_REVIEW_ENABLED = True
    settings.AI_REVIEW_AUTO_NUDGE = 'off'   # keep status assertions simple
    yield
    ai_review._reset_for_tests()
    contributions._reset_for_tests()


def test_real_chain_returns_contract_valid_verdict(real_reviewer):
    """Direct ``_call_llm_with_fallback`` over the real composed prompt."""
    assert ai_review.init_reviewer() is True

    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(), original_filename='real.zip',
    )
    prompt = ai_review._compose_prompt(sub['id'])
    assert 'SKILL.md' in prompt

    verdict = ai_review._call_llm_with_fallback(
        prompt, ai_review._config.models,
    )

    if verdict.error_type == 'rate_limit':
        pytest.skip('free-tier chain exhausted by 429s — retry later')

    _assert_verdict_contract(verdict)
    assert verdict.model, 'verdict must name the model that produced it'


def test_real_full_pipeline_posts_renderable_comment(real_reviewer):
    """submit → enqueue → worker → live LLM → ai_reviewer comment."""
    assert ai_review.init_reviewer() is True

    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(name='real-pipeline-skill'),
        original_filename='pipeline.zip',
    )
    ai_review.enqueue_review(sub['id'])

    found = _wait_until(
        lambda: any(
            c['authorRole'] == contributions.ROLE_AI_REVIEWER
            for c in contributions.get_submission(sub['id'])['comments']
        ),
        timeout_s=_REAL_CALL_TIMEOUT_S,
    )
    assert found, 'no ai_reviewer comment within timeout'

    full = contributions.get_submission(sub['id'])
    assert full['last_ai_review_ts'] is not None

    extracted = views._extract_ai_verdict(full['comments'])
    if extracted is None:
        # Defensive: chain exhausted by rate limits still posts a
        # needs_human_review comment, which must extract. If it didn't,
        # that IS a bug — fail with the body for diagnosis.
        ai_body = next(
            c['body'] for c in full['comments']
            if c['authorRole'] == contributions.ROLE_AI_REVIEWER
        )
        pytest.fail(f'ai_reviewer comment did not extract:\n{ai_body[:800]}')
    assert extracted['overall'] in _VALID_OVERALLS
    assert 0.0 <= extracted['confidence'] <= 1.0
