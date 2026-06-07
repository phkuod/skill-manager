"""M3 — real LLM call + tolerant JSON parser + Pydantic validation.

Tests live entirely against the module boundary: the tolerant parser is
called directly with synthetic strings, and ``_call_llm`` is exercised
against a hand-rolled mock that stands in for the OpenAI SDK so we
never touch the network. The opt-in real-OpenRouter tests live in
``test_ai_review_e2e_real.py`` (M3c).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from skills import ai_review


# ─── _tolerant_json_load ──────────────────────────────────────────────────


def test_parser_strict_json_succeeds():
    assert ai_review._tolerant_json_load('{"a": 1}') == {'a': 1}


def test_parser_strips_markdown_fence_with_lang():
    raw = '```json\n{"a": 2}\n```'
    assert ai_review._tolerant_json_load(raw) == {'a': 2}


def test_parser_strips_generic_fence():
    raw = '```\n{"a": 3}\n```'
    assert ai_review._tolerant_json_load(raw) == {'a': 3}


def test_parser_extracts_first_brace_block_from_prose():
    raw = 'Sure! Here is the JSON:\n{"a": 4, "b": [1,2,3]}\nLet me know.'
    assert ai_review._tolerant_json_load(raw) == {'a': 4, 'b': [1, 2, 3]}


def test_parser_raises_on_pure_prose():
    with pytest.raises(ValueError):
        ai_review._tolerant_json_load(
            'Hi, I cannot produce JSON right now. Maybe try again later.'
        )


def test_parser_raises_on_empty():
    with pytest.raises(ValueError):
        ai_review._tolerant_json_load('')
    with pytest.raises(ValueError):
        ai_review._tolerant_json_load('   \n  ')
    with pytest.raises(ValueError):
        ai_review._tolerant_json_load(None)


# ─── _VerdictSchema validation ───────────────────────────────────────────────


def _valid_payload(**overrides):
    base = {
        'overall': 'approve',
        'confidence': 0.8,
        'summary': 'looks clean',
        'findings': [],
        'checks_passed': ['no_eval'],
    }
    base.update(overrides)
    return base


def test_pydantic_accepts_minimal_payload():
    schema = ai_review._VerdictSchema(**_valid_payload())
    assert schema.overall == 'approve'
    assert schema.confidence == 0.8


def test_pydantic_rejects_unknown_overall():
    with pytest.raises((ValueError, ValidationError)):
        ai_review._VerdictSchema(**_valid_payload(overall='maybe'))


def test_pydantic_rejects_out_of_range_confidence():
    with pytest.raises((ValueError, ValidationError)):
        ai_review._VerdictSchema(**_valid_payload(confidence=1.7))
    with pytest.raises((ValueError, ValidationError)):
        ai_review._VerdictSchema(**_valid_payload(confidence=-0.1))


def test_pydantic_rejects_unknown_severity_in_finding():
    payload = _valid_payload(findings=[
        {'severity': 'catastrophic', 'category': 'security', 'title': 'x'},
    ])
    with pytest.raises((ValueError, ValidationError)):
        ai_review._VerdictSchema(**payload)


def test_pydantic_rejects_unknown_category_in_finding():
    payload = _valid_payload(findings=[
        {'severity': 'warn', 'category': 'aesthetics', 'title': 'x'},
    ])
    with pytest.raises((ValueError, ValidationError)):
        ai_review._VerdictSchema(**payload)


def test_pydantic_rejects_findings_over_cap_of_20():
    payload = _valid_payload(findings=[
        {'severity': 'note', 'category': 'quality', 'title': f't{i}'}
        for i in range(21)
    ])
    with pytest.raises((ValueError, ValidationError)):
        ai_review._VerdictSchema(**payload)


# ─── _call_llm: stub fallback when no API key ────────────────────────────


def test_call_llm_returns_stub_when_no_api_key(monkeypatch, settings):
    ai_review._reset_for_tests()
    # Drive a config with no api_key. _call_llm should never touch SDK.
    settings.AI_REVIEW_ENABLED = True
    settings.LLM_BASE_URL = 'http://stub'
    settings.LLM_API_KEY = ''
    settings.AI_REVIEW_MODELS = ['stub-model']
    ai_review._config = ai_review._build_config()

    verdict = ai_review._call_llm('hello prompt', 'stub-model')
    assert verdict.overall == 'approve'
    assert 'Stub verdict' in verdict.summary
    assert verdict.findings == []
    ai_review._reset_for_tests()


# ─── _call_llm: mocked real path ─────────────────────────────────────────


class _FakeMessage:
    def __init__(self, content): self.content = content


class _FakeChoice:
    def __init__(self, content): self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content): self.choices = [_FakeChoice(content)]


class _FakeChatCompletions:
    """Records calls + plays back responses in order."""
    def __init__(self, responses):
        self._responses = list(responses)   # consume
        self.calls = []   # list of (model, messages) pairs

    def create(self, *, model, messages, response_format=None,
               temperature=None, max_tokens=None):
        self.calls.append((model, messages))
        if not self._responses:
            raise RuntimeError('test fixture ran out of responses')
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return _FakeResponse(nxt)


class _FakeClient:
    def __init__(self, responses):
        self.chat = type('C', (), {'completions': _FakeChatCompletions(responses)})()


@pytest.fixture
def real_path_config(monkeypatch, settings):
    """Config with api_key set so _call_llm takes the real path."""
    ai_review._reset_for_tests()
    settings.AI_REVIEW_ENABLED = True
    settings.LLM_BASE_URL = 'http://stub'
    settings.LLM_API_KEY = 'sk-test'
    settings.AI_REVIEW_MODELS = ['fake-model']
    ai_review._config = ai_review._build_config()
    yield
    ai_review._reset_for_tests()


def _install_fake_client(monkeypatch, responses):
    fake = _FakeClient(responses)
    monkeypatch.setattr(ai_review, '_get_client', lambda: fake)
    return fake


def test_call_llm_happy_path_returns_validated_verdict(real_path_config, monkeypatch):
    good_json = (
        '{"overall": "approve", "confidence": 0.92, '
        '"summary": "Clean.", "findings": [], "checks_passed": ["no_eval"]}'
    )
    _install_fake_client(monkeypatch, [good_json])

    verdict = ai_review._call_llm('the composed prompt', 'fake-model')
    assert verdict.overall == 'approve'
    assert verdict.confidence == 0.92
    assert 'Clean' in verdict.summary
    assert verdict.findings == []
    assert verdict.model == 'fake-model'


def test_call_llm_strips_code_fences_via_tolerant_parser(real_path_config, monkeypatch):
    fenced = (
        '```json\n'
        '{"overall": "request_changes", "confidence": 0.6, '
        '"summary": "fix license", "findings": [], "checks_passed": []}\n'
        '```'
    )
    _install_fake_client(monkeypatch, [fenced])
    verdict = ai_review._call_llm('prompt', 'fake-model')
    assert verdict.overall == 'request_changes'


def test_call_llm_reprompts_on_first_parse_failure(real_path_config, monkeypatch):
    """Garbage → reprompt → success."""
    second = (
        '{"overall": "approve", "confidence": 0.7, '
        '"summary": "ok after retry", "findings": [], "checks_passed": []}'
    )
    fake = _install_fake_client(monkeypatch, ['no json here, just prose', second])

    verdict = ai_review._call_llm('prompt', 'fake-model')
    assert verdict.overall == 'approve'
    assert 'after retry' in verdict.summary
    # Two SDK calls (initial + reprompt) and the reprompt user message
    # contains the JSON-only kicker.
    assert len(fake.chat.completions.calls) == 2
    second_user = fake.chat.completions.calls[1][1][1]['content']
    assert 'JSON only' in second_user or 'JSON' in second_user


def test_call_llm_yields_needs_human_review_when_both_attempts_fail(
    real_path_config, monkeypatch,
):
    fake = _install_fake_client(
        monkeypatch,
        ['totally not json', 'still not json after retry'],
    )
    verdict = ai_review._call_llm('prompt', 'fake-model')
    assert verdict.overall == 'needs_human_review'
    assert verdict.confidence == 0.0
    assert 'could not be parsed' in verdict.summary
    assert verdict.raw_text is not None
    # The raw text from the SECOND (retry) attempt is the one we preserve
    # since it's the most recent.
    assert 'after retry' in verdict.raw_text


def test_call_llm_yields_needs_human_review_on_sdk_exception(
    real_path_config, monkeypatch,
):
    """All SDK errors are caught and surface as needs_human_review."""
    _install_fake_client(
        monkeypatch,
        [RuntimeError('connection refused'), RuntimeError('still down')],
    )
    verdict = ai_review._call_llm('prompt', 'fake-model')
    assert verdict.overall == 'needs_human_review'
    assert verdict.raw_text is None    # no raw text when the SDK never returned


def test_call_llm_validates_against_pydantic_schema(real_path_config, monkeypatch):
    """JSON that parses but fails the schema (bad overall) → reprompt."""
    invalid = '{"overall": "maybe", "confidence": 0.5, "summary": "x"}'
    valid_retry = (
        '{"overall": "reject", "confidence": 0.55, '
        '"summary": "policy block", "findings": [], "checks_passed": []}'
    )
    fake = _install_fake_client(monkeypatch, [invalid, valid_retry])
    verdict = ai_review._call_llm('prompt', 'fake-model')
    assert verdict.overall == 'reject'
    assert len(fake.chat.completions.calls) == 2


def test_call_llm_raw_text_truncated_to_2kb_on_total_failure(
    real_path_config, monkeypatch,
):
    huge = 'A' * 5000
    _install_fake_client(monkeypatch, [huge, huge])
    verdict = ai_review._call_llm('prompt', 'fake-model')
    assert verdict.raw_text is not None
    assert len(verdict.raw_text) <= 2100   # 2000 + the truncation tail
    assert verdict.raw_text.endswith('…(truncated)')
