"""M0 — settings + dark switch + empty lifecycle.

These tests pin the configuration-parsing layer and the dark-switched
``init_reviewer`` / ``shutdown`` contract. They never touch the
network, the LLM client, the worker thread, or the contributions DB —
all of that arrives in M1.
"""
import pytest
from django.conf import settings as django_settings

from skills import ai_review


@pytest.fixture
def fresh_reviewer():
    """Tear down ai_review module state before and after each test."""
    ai_review._reset_for_tests()
    yield
    ai_review._reset_for_tests()


# ── lifecycle ────────────────────────────────────────────────────────────────


def test_init_returns_false_when_disabled(fresh_reviewer, settings):
    settings.AI_REVIEW_ENABLED = False
    assert ai_review.init_reviewer() is False


def test_init_returns_true_when_enabled_with_minimal_valid_config(
    fresh_reviewer, settings
):
    settings.AI_REVIEW_ENABLED = True
    settings.LLM_BASE_URL = 'https://openrouter.ai/api/v1'
    settings.LLM_API_KEY = 'sk-test'
    settings.AI_REVIEW_MODELS = ['stub-model']
    assert ai_review.init_reviewer() is True


def test_init_is_idempotent_when_called_twice(fresh_reviewer, settings):
    settings.AI_REVIEW_ENABLED = True
    settings.LLM_BASE_URL = 'https://openrouter.ai/api/v1'
    settings.LLM_API_KEY = 'sk-test'
    settings.AI_REVIEW_MODELS = ['stub-model']
    first = ai_review.init_reviewer()
    second = ai_review.init_reviewer()
    assert first is True
    assert second is True   # second call observes _initialized + returns same


def test_shutdown_is_safe_when_init_was_never_called(fresh_reviewer):
    # Should not raise even though we never called init_reviewer().
    ai_review.shutdown()


def test_shutdown_is_safe_when_init_returned_false(fresh_reviewer, settings):
    settings.AI_REVIEW_ENABLED = False
    ai_review.init_reviewer()
    ai_review.shutdown()


# ── settings defaults (pinned so we notice if anyone changes them) ───────────


def test_settings_default_ai_review_enabled_is_false():
    # Dark by default — feature ships off, ops flips it on.
    assert django_settings.AI_REVIEW_ENABLED is False


def test_settings_default_models_chain_is_nonempty_list():
    assert isinstance(django_settings.AI_REVIEW_MODELS, list)
    assert len(django_settings.AI_REVIEW_MODELS) >= 1


def test_settings_confidence_cap_defaults_to_zero_point_eight():
    # Calibrated for noisier free-tier models; relax on internal endpoint.
    assert django_settings.AI_REVIEW_CONFIDENCE_CAP == 0.8


def test_settings_concurrent_workers_defaults_to_one():
    # Single-process Django pinned to one gunicorn worker; matches.
    assert django_settings.AI_REVIEW_CONCURRENT_WORKERS == 1


def test_settings_max_input_tokens_defaults_to_twelve_thousand():
    assert django_settings.AI_REVIEW_MAX_INPUT_TOKENS == 12000


# ── parsing helpers ─────────────────────────────────────────────────────────


def test_parses_llm_extra_headers_comma_separated():
    # "HTTP-Referer=https://x,X-Title=AI reviewer" → {"HTTP-Referer": "https://x", ...}
    parsed = ai_review._parse_extra_headers(
        'HTTP-Referer=https://skills.local,X-Title=AI reviewer'
    )
    assert parsed == {
        'HTTP-Referer': 'https://skills.local',
        'X-Title': 'AI reviewer',
    }
    assert ai_review._parse_extra_headers('') == {}
    assert ai_review._parse_extra_headers(None) == {}
