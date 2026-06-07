"""M3c — model fallback chain + rate budget + hallucinated-evidence drop.

Three concerns in one file because they're tightly related: the chain
wrapper drives the rate budget, the rate budget's state shapes the
chain's choices, and the hallucinated-evidence drop pass sits at the
end of ``_run_review`` next to both.

All LLM behaviour is faked at the ``_call_llm`` boundary (via
monkeypatch) so the chain can be driven model-by-model. No network.
"""
from __future__ import annotations

import pytest

from skills import ai_review


# ─── _RateBudget ──────────────────────────────────────────────────────────


def test_rate_budget_take_allows_under_cap():
    rb = ai_review._RateBudget(per_min=3)
    assert rb.take('m1') is True
    assert rb.take('m1') is True
    assert rb.take('m1') is True


def test_rate_budget_take_denies_when_cap_hit():
    rb = ai_review._RateBudget(per_min=2)
    assert rb.take('m1') is True
    assert rb.take('m1') is True
    assert rb.take('m1') is False    # over cap


def test_rate_budget_take_zero_disables_budget():
    rb = ai_review._RateBudget(per_min=0)
    for _ in range(50):
        assert rb.take('m1') is True


def test_rate_budget_per_model_independent():
    rb = ai_review._RateBudget(per_min=1)
    assert rb.take('m1') is True
    assert rb.take('m1') is False
    assert rb.take('m2') is True       # m2 is independent
    assert rb.take('m2') is False


def test_rate_budget_record_429_then_is_cooled():
    rb = ai_review._RateBudget(per_min=10, cooloff_seconds=60)
    assert rb.is_cooled('m1') is False
    rb.record_429('m1')
    assert rb.is_cooled('m1') is True
    assert rb.is_cooled('m2') is False   # only m1 cooled


def test_rate_budget_cooloff_lifts_after_period(monkeypatch):
    """Fast-forward _RateBudget's clock with a fake time source."""
    fake_t = [1000.0]
    monkeypatch.setattr(ai_review.time, 'monotonic', lambda: fake_t[0])
    rb = ai_review._RateBudget(per_min=10, cooloff_seconds=30)
    rb.record_429('m1')
    assert rb.is_cooled('m1') is True
    fake_t[0] += 31
    assert rb.is_cooled('m1') is False


# ─── _call_llm_with_fallback (chain walker) ─────────────────────────────


def _verdict(overall='approve', error_type=None, model='m', findings=None):
    return ai_review._Verdict(
        overall=overall,
        confidence=0.8,
        summary='ok',
        findings=findings or [],
        model=model,
        error_type=error_type,
    )


@pytest.fixture
def fresh_budget(monkeypatch):
    """Install a fresh _RateBudget on the module so chain tests don't
    inherit cool-off / call history from earlier tests."""
    rb = ai_review._RateBudget(per_min=100, cooloff_seconds=30)
    monkeypatch.setattr(ai_review, '_rate_budget', rb)
    return rb


def test_chain_returns_first_success(monkeypatch, fresh_budget):
    """Happy path — first model returns a legitimate verdict, chain stops."""
    calls = []

    def fake_call(prompt, model):
        calls.append(model)
        return _verdict(overall='approve', model=model)

    monkeypatch.setattr(ai_review, '_call_llm', fake_call)
    verdict = ai_review._call_llm_with_fallback(
        'prompt', ['m1', 'm2', 'm3'],
    )
    assert verdict.overall == 'approve'
    assert verdict.model == 'm1'
    assert calls == ['m1']


def test_chain_walks_past_sdk_error(monkeypatch, fresh_budget):
    def fake_call(prompt, model):
        if model == 'm1':
            return _verdict(overall='needs_human_review',
                            error_type='sdk_error', model='m1')
        return _verdict(overall='approve', model='m2')

    monkeypatch.setattr(ai_review, '_call_llm', fake_call)
    verdict = ai_review._call_llm_with_fallback(
        'prompt', ['m1', 'm2'],
    )
    assert verdict.overall == 'approve'
    assert verdict.model == 'm2'


def test_chain_records_cooloff_on_rate_limit(monkeypatch, fresh_budget):
    def fake_call(prompt, model):
        if model == 'm1':
            return _verdict(overall='needs_human_review',
                            error_type='rate_limit', model='m1')
        return _verdict(overall='approve', model='m2')

    monkeypatch.setattr(ai_review, '_call_llm', fake_call)
    ai_review._call_llm_with_fallback('prompt', ['m1', 'm2'])
    assert fresh_budget.is_cooled('m1') is True
    assert fresh_budget.is_cooled('m2') is False


def test_chain_skips_cooled_models(monkeypatch, fresh_budget):
    """Pre-cool m1; chain should skip straight to m2."""
    fresh_budget.record_429('m1')

    calls = []
    def fake_call(prompt, model):
        calls.append(model)
        return _verdict(overall='approve', model=model)

    monkeypatch.setattr(ai_review, '_call_llm', fake_call)
    verdict = ai_review._call_llm_with_fallback(
        'prompt', ['m1', 'm2'],
    )
    assert calls == ['m2']     # m1 skipped entirely
    assert verdict.model == 'm2'


def test_chain_skips_when_rate_budget_exhausted(monkeypatch):
    """A model that fails take() is skipped without a _call_llm call."""
    # Budget of 1: first attempt consumes, second call to take() denies.
    rb = ai_review._RateBudget(per_min=1, cooloff_seconds=30)
    rb.take('m1')   # pre-exhaust m1's budget
    monkeypatch.setattr(ai_review, '_rate_budget', rb)

    calls = []
    def fake_call(prompt, model):
        calls.append(model)
        return _verdict(overall='approve', model=model)

    monkeypatch.setattr(ai_review, '_call_llm', fake_call)
    verdict = ai_review._call_llm_with_fallback(
        'prompt', ['m1', 'm2'],
    )
    assert calls == ['m2']
    assert verdict.model == 'm2'


def test_chain_walks_past_parse_failure(monkeypatch, fresh_budget):
    def fake_call(prompt, model):
        if model == 'm1':
            return _verdict(overall='needs_human_review',
                            error_type='parse_failure', model='m1')
        return _verdict(overall='approve', model='m2')

    monkeypatch.setattr(ai_review, '_call_llm', fake_call)
    verdict = ai_review._call_llm_with_fallback(
        'prompt', ['m1', 'm2'],
    )
    assert verdict.overall == 'approve'
    assert verdict.model == 'm2'


def test_chain_does_not_retry_legitimate_needs_human_review(monkeypatch, fresh_budget):
    """A model with error_type=None saying needs_human_review is final."""
    calls = []
    def fake_call(prompt, model):
        calls.append(model)
        return _verdict(overall='needs_human_review', error_type=None,
                        model=model)

    monkeypatch.setattr(ai_review, '_call_llm', fake_call)
    verdict = ai_review._call_llm_with_fallback(
        'prompt', ['m1', 'm2'],
    )
    assert calls == ['m1']
    assert verdict.overall == 'needs_human_review'
    assert verdict.error_type is None


def test_chain_returns_synthesized_when_all_models_fail(monkeypatch, fresh_budget):
    def fake_call(prompt, model):
        return _verdict(overall='needs_human_review',
                        error_type='sdk_error', model=model)

    monkeypatch.setattr(ai_review, '_call_llm', fake_call)
    verdict = ai_review._call_llm_with_fallback(
        'prompt', ['m1', 'm2'],
    )
    assert verdict.overall == 'needs_human_review'
    assert 'exhausted' in verdict.summary
    assert verdict.error_type == 'sdk_error'


def test_chain_returns_synthesized_when_every_model_skipped(monkeypatch):
    """Every model is cooled; chain never invokes _call_llm."""
    rb = ai_review._RateBudget(per_min=10, cooloff_seconds=30)
    rb.record_429('m1')
    rb.record_429('m2')
    monkeypatch.setattr(ai_review, '_rate_budget', rb)

    calls = []
    def fake_call(prompt, model):
        calls.append(model)
        return _verdict()
    monkeypatch.setattr(ai_review, '_call_llm', fake_call)

    verdict = ai_review._call_llm_with_fallback('prompt', ['m1', 'm2'])
    assert calls == []
    assert verdict.overall == 'needs_human_review'
    assert verdict.error_type == 'rate_limit'


def test_chain_empty_models_list_returns_synthesized(monkeypatch, fresh_budget):
    verdict = ai_review._call_llm_with_fallback('prompt', [])
    assert verdict.overall == 'needs_human_review'
    assert 'no models' in verdict.summary


# ─── _drop_hallucinated_evidence ────────────────────────────────────────


def _make_config_with_drop(enabled: bool):
    """Hand-roll a minimal _Config snapshot just for the drop pass."""
    cfg = ai_review._Config(
        base_url='http://stub', api_key='k', extra_headers={},
        models=['m'], max_input_tokens=12000, timeout_s=10,
        rate_budget_per_min=15, concurrent_workers=1, auto_nudge='always',
        confidence_cap=0.8, drop_hallucinated_evidence=enabled,
        privacy_notice='', rerun_daily_cap=3, catalog_detail='hashes',
    )
    return cfg


def test_drop_keeps_findings_with_paths_in_bundle(monkeypatch):
    monkeypatch.setattr(ai_review, '_config', _make_config_with_drop(True))
    verdict = _verdict(findings=[
        {'severity': 'warn', 'category': 'security',
         'title': 'eval call', 'evidence': 'handlers/main.py:42'},
    ])
    bundle = {
        'file_tree': [{'relPath': 'handlers/main.py', 'size': 100}],
        'code_excerpts': [],
    }
    result = ai_review._drop_hallucinated_evidence(verdict, bundle)
    assert len(result.findings) == 1


def test_drop_strips_findings_with_invented_paths(monkeypatch):
    monkeypatch.setattr(ai_review, '_config', _make_config_with_drop(True))
    verdict = _verdict(findings=[
        {'severity': 'block', 'category': 'security',
         'title': 'fake', 'evidence': 'secrets/bogus.py:1'},
    ])
    bundle = {
        'file_tree': [{'relPath': 'handlers/main.py', 'size': 100}],
        'code_excerpts': [],
    }
    result = ai_review._drop_hallucinated_evidence(verdict, bundle)
    assert result.findings == []


def test_drop_keeps_findings_with_null_evidence(monkeypatch):
    monkeypatch.setattr(ai_review, '_config', _make_config_with_drop(True))
    verdict = _verdict(findings=[
        {'severity': 'note', 'category': 'quality',
         'title': 'description short', 'evidence': None},
    ])
    bundle = {'file_tree': [], 'code_excerpts': []}
    result = ai_review._drop_hallucinated_evidence(verdict, bundle)
    assert len(result.findings) == 1


def test_drop_disabled_by_setting_keeps_everything(monkeypatch):
    monkeypatch.setattr(ai_review, '_config', _make_config_with_drop(False))
    verdict = _verdict(findings=[
        {'severity': 'block', 'category': 'security',
         'title': 'invented', 'evidence': 'nope.py:1'},
    ])
    bundle = {'file_tree': [{'relPath': 'real.py', 'size': 10}],
              'code_excerpts': []}
    result = ai_review._drop_hallucinated_evidence(verdict, bundle)
    assert len(result.findings) == 1


def test_drop_accepts_suffix_match(monkeypatch):
    """A model citing 'main.py:14' should match 'handlers/main.py' in bundle."""
    monkeypatch.setattr(ai_review, '_config', _make_config_with_drop(True))
    verdict = _verdict(findings=[
        {'severity': 'warn', 'category': 'quality',
         'title': 'unused', 'evidence': 'main.py:14'},
    ])
    bundle = {
        'file_tree': [{'relPath': 'handlers/main.py', 'size': 100}],
        'code_excerpts': [],
    }
    result = ai_review._drop_hallucinated_evidence(verdict, bundle)
    assert len(result.findings) == 1


def test_drop_handles_empty_bundle(monkeypatch):
    monkeypatch.setattr(ai_review, '_config', _make_config_with_drop(True))
    verdict = _verdict(findings=[
        {'severity': 'note', 'category': 'quality',
         'title': 'x', 'evidence': 'a.py'},
    ])
    # Empty bundle, drop ON → all path-citing findings dropped.
    result = ai_review._drop_hallucinated_evidence(verdict, {})
    assert result.findings == []
