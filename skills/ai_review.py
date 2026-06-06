"""AI reviewer for user-contributed skills (phase 2).

This module is the asynchronous LLM-driven co-pilot for the admin: when a
submission lands, a background worker walks the model fallback chain,
gathers bundle context, and posts a structured findings comment on the
submission timeline. The admin still owns the approve/reject/publish
decision — the AI never mutates status beyond a soft nudge into
``under_review``.

M0 scope (this commit): settings parsing, dark switch, idempotent
lifecycle hooks. The module is intentionally a no-op when
``AI_REVIEW_ENABLED=false`` so the feature can ship dark and ride into
prod behind an env-var flip. M1 brings the in-memory queue + worker
thread; M2 adds bundle gathering; M3 wires the real LLM call.

The shape (init / shutdown / module-level state / _reset_for_tests)
mirrors ``skills.usage`` and ``skills.contributions`` so the lazy-init
pattern in ``skills.apps._init_once`` stays uniform.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger('skills.ai_review')


# ── module state ────────────────────────────────────────────────────────────

_lock = threading.Lock()
_initialized = False
_disabled = False
_config: "_Config | None" = None


@dataclass
class _Config:
    """Snapshot of the AI-reviewer settings, frozen at init time.

    We read settings once into this dataclass so the worker thread isn't
    paying for repeated ``django.conf.settings`` lookups on every call,
    and so mid-run env changes don't silently take effect.
    """
    base_url: str
    api_key: str
    extra_headers: dict
    models: list
    max_input_tokens: int
    timeout_s: int
    rate_budget_per_min: int
    concurrent_workers: int
    auto_nudge: str
    confidence_cap: float
    drop_hallucinated_evidence: bool
    privacy_notice: str
    rerun_daily_cap: int
    catalog_detail: str   # 'hashes' | 'full'


# ── parsing helpers ─────────────────────────────────────────────────────────


def _parse_extra_headers(raw):
    """Turn ``"k1=v1,k2=v2"`` into ``{"k1": "v1", "k2": "v2"}``.

    Empty/None → ``{}``. Leading/trailing whitespace stripped. Pairs
    missing an ``=`` are skipped silently — they're operator typos and
    should not crash boot.
    """
    if not raw:
        return {}
    out = {}
    for pair in raw.split(','):
        pair = pair.strip()
        if '=' not in pair:
            continue
        k, _, v = pair.partition('=')
        k = k.strip()
        v = v.strip()
        if k:
            out[k] = v
    return out


def _build_config():
    """Read django.conf.settings once into the frozen _Config snapshot."""
    from django.conf import settings as s
    return _Config(
        base_url=getattr(s, 'LLM_BASE_URL', ''),
        api_key=getattr(s, 'LLM_API_KEY', ''),
        extra_headers=_parse_extra_headers(getattr(s, 'LLM_EXTRA_HEADERS', '')),
        models=list(getattr(s, 'AI_REVIEW_MODELS', [])),
        max_input_tokens=int(getattr(s, 'AI_REVIEW_MAX_INPUT_TOKENS', 12000)),
        timeout_s=int(getattr(s, 'AI_REVIEW_TIMEOUT_S', 120)),
        rate_budget_per_min=int(getattr(s, 'AI_REVIEW_RATE_BUDGET_PER_MIN', 15)),
        concurrent_workers=int(getattr(s, 'AI_REVIEW_CONCURRENT_WORKERS', 1)),
        auto_nudge=getattr(s, 'AI_REVIEW_AUTO_NUDGE', 'always'),
        confidence_cap=float(getattr(s, 'AI_REVIEW_CONFIDENCE_CAP', 0.8)),
        drop_hallucinated_evidence=bool(
            getattr(s, 'AI_REVIEW_DROP_HALLUCINATED_EVIDENCE', True)
        ),
        privacy_notice=getattr(s, 'AI_REVIEW_PRIVACY_NOTICE', ''),
        rerun_daily_cap=int(
            getattr(s, 'AI_REVIEW_RERUN_DAILY_CAP_PER_SUBMISSION', 3)
        ),
        catalog_detail=getattr(s, 'AI_REVIEW_CATALOG_DETAIL', 'hashes'),
    )


# ── lifecycle ────────────────────────────────────────────────────────────────


def init_reviewer():
    """Bring the AI reviewer up.

    Idempotent — safe to call repeatedly from the lazy-init hook in
    ``skills.apps._init_once``. Returns:

    * ``False`` when ``AI_REVIEW_ENABLED=false`` (dark switch). The
      module stays disabled; nothing else happens.
    * ``False`` when configuration is invalid (e.g. enabled but no
      models in the chain). One ERROR-level log; the module disables
      itself so the rest of the app keeps working.
    * ``True`` when initialisation succeeded.

    M0 builds the config snapshot and stops. M1+ will add: ALTER TABLE
    for ``submissions.last_ai_review_ts``, OpenAI client construction,
    worker thread spawn, and orphan scan.
    """
    global _initialized, _disabled, _config

    with _lock:
        if _initialized:
            return not _disabled

        from django.conf import settings as s
        if not getattr(s, 'AI_REVIEW_ENABLED', False):
            _initialized = True
            _disabled = True
            logger.info('AI reviewer disabled (AI_REVIEW_ENABLED=false)')
            return False

        cfg = _build_config()
        if not cfg.models:
            _initialized = True
            _disabled = True
            logger.error(
                'AI reviewer enabled but AI_REVIEW_MODELS is empty — disabled'
            )
            return False

        _initialized = True
        _disabled = False
        _config = cfg

    logger.info(
        'AI reviewer ready (base_url=%s, models=%d, workers=%d) — M0 stub',
        cfg.base_url, len(cfg.models), cfg.concurrent_workers,
    )
    return True


def shutdown():
    """Tear down the reviewer cleanly.

    Safe to call even when ``init_reviewer`` was never invoked or
    returned ``False`` (dark switch / config error). M1 will signal the
    worker thread to stop and wait briefly for it to drain.
    """
    with _lock:
        if not _initialized:
            return
        # Nothing else to tear down at M0.


def _reset_for_tests():
    """Wipe module state. Tests only — mirrors ``usage._reset_for_tests``."""
    global _initialized, _disabled, _config
    with _lock:
        _initialized = False
        _disabled = False
        _config = None
