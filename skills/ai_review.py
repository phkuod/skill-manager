"""AI reviewer for user-contributed skills (phase 2).

This module is the asynchronous LLM-driven co-pilot for the admin: when a
submission lands, a background worker walks the model fallback chain,
gathers bundle context, and posts a structured findings comment on the
submission timeline. The admin still owns the approve/reject/publish
decision — the AI never mutates status beyond a soft nudge into
``under_review``.

Milestones:

* **M0** — settings parsing, dark switch, idempotent lifecycle hooks.
* **M1** *(this commit)* — in-memory queue, single daemon worker thread,
  ``enqueue_review`` public API, orphan-scan recovery on startup, stub
  ``_call_llm`` that returns a canned ``approve`` verdict so the
  end-to-end persistence path (verdict → ai_reviewer comment →
  ``last_ai_review_ts`` stamp) can be exercised without real network.
* **M2** — bundle context gathering + catalog index.
* **M3a–c** — real OpenAI-SDK call against OpenRouter / internal endpoint;
  tolerant JSON parser; model fallback chain with rate-budget cool-off.

The shape (init / shutdown / module-level state / ``_reset_for_tests``)
mirrors ``skills.usage`` and ``skills.contributions`` so the lazy-init
pattern in ``skills.apps._init_once`` stays uniform.

The whole module is a no-op when ``AI_REVIEW_ENABLED=false``. Workers
never start, ``enqueue_review`` returns immediately, the shutdown path
is safe. This is what lets the feature ride into prod behind a single
env-var flip.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger('skills.ai_review')


# ── module state ────────────────────────────────────────────────────────────

_lock = threading.Lock()                          # guards lifecycle flags
_initialized = False
_disabled = False
_config: "_Config | None" = None
_queue: "queue.Queue[int] | None" = None          # in-memory FIFO of sub_ids
_stop = threading.Event()                         # set on shutdown
_workers: list = []                               # daemon worker Threads

# Worker pool exits faster than this when the queue is idle and shutdown is
# signalled. Each iteration polls _stop, so the actual stop latency is at
# most _QUEUE_GET_TIMEOUT_S.
_QUEUE_GET_TIMEOUT_S = 1.0
_SHUTDOWN_JOIN_TIMEOUT_S = 3.0


# ── dataclasses ─────────────────────────────────────────────────────────────


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


@dataclass
class _Verdict:
    """Structured AI verdict for one submission.

    M1 ships with a plain dataclass; M3 will swap for a Pydantic model so
    the LLM response can be schema-validated and re-prompted on failure.
    The on-disk representation is the rendered Markdown comment body —
    this dataclass is only used in-memory between ``_call_llm`` and
    ``_render_comment_body``.
    """
    overall: str          # 'approve' | 'request_changes' | 'reject' | 'needs_human_review'
    confidence: float     # 0.0 – 1.0
    summary: str          # one-paragraph executive summary for the admin
    findings: list = field(default_factory=list)
    model: str = ''       # which model produced this verdict
    latency_s: float = 0.0


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

    * ``False`` when ``AI_REVIEW_ENABLED=false`` (dark switch). No
      worker threads, no queue, no DB touchpoints.
    * ``False`` when configuration is invalid (e.g. enabled but no
      models in the chain). One ERROR-level log; the module disables
      itself so the rest of the app keeps working.
    * ``True`` when initialisation succeeded — worker thread(s) running,
      queue ready, orphan scan complete.
    """
    global _initialized, _disabled, _config, _queue, _stop

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
        _queue = queue.Queue()
        _stop = threading.Event()
        for i in range(cfg.concurrent_workers):
            t = threading.Thread(
                target=_worker_loop,
                name=f'ai-review-{i + 1}',
                daemon=True,
            )
            t.start()
            _workers.append(t)

    # Orphan recovery runs outside _lock so the worker can pick up while
    # we're still enumerating. List operation is cheap; safe to call even
    # if contributions hasn't been initialised (we swallow and log).
    _scan_orphans()

    logger.info(
        'AI reviewer ready (base_url=%s, models=%d, workers=%d)',
        cfg.base_url, len(cfg.models), cfg.concurrent_workers,
    )
    return True


def shutdown():
    """Tear down the reviewer cleanly.

    Safe to call even when ``init_reviewer`` was never invoked or
    returned ``False`` (dark switch / config error). Signals the worker
    thread(s) to stop and waits up to ``_SHUTDOWN_JOIN_TIMEOUT_S``
    seconds for them to drain.
    """
    global _workers
    with _lock:
        if not _initialized or _disabled:
            return
        _stop.set()
        workers_snapshot = list(_workers)

    for t in workers_snapshot:
        t.join(timeout=_SHUTDOWN_JOIN_TIMEOUT_S)

    with _lock:
        _workers = []


def _reset_for_tests():
    """Wipe module state. Tests only — mirrors ``usage._reset_for_tests``.

    Halts the worker thread(s) if any are running and clears every
    module-level reference so the next ``init_reviewer`` starts from a
    pristine state. Idempotent.
    """
    global _initialized, _disabled, _config, _queue, _workers
    # Trigger graceful shutdown if we're running, without holding the lock
    # across the join (which would deadlock the workers polling _stop).
    if _initialized and not _disabled:
        shutdown()
    with _lock:
        _initialized = False
        _disabled = False
        _config = None
        _queue = None
        _workers = []
        _stop.clear()


# ── enqueue API ─────────────────────────────────────────────────────────────


def enqueue_review(submission_id):
    """Schedule a submission for AI review.

    Non-blocking — pushes the id into the worker queue and returns
    immediately. A no-op when the reviewer is disabled, so callers
    (notably ``views.api_contribute_submit``) can fire-and-forget without
    branching on ``AI_REVIEW_ENABLED``.
    """
    if _disabled or _queue is None:
        return
    _queue.put(int(submission_id))


# ── worker loop ─────────────────────────────────────────────────────────────


def _worker_loop():
    """Daemon thread main: pop ids off the queue, hand each to _run_review.

    Exceptions inside ``_run_review`` are logged and swallowed — one bad
    submission must not kill the worker. The loop exits cleanly when
    ``_stop`` is set, at most ``_QUEUE_GET_TIMEOUT_S`` after the signal.
    """
    while not _stop.is_set():
        try:
            sub_id = _queue.get(timeout=_QUEUE_GET_TIMEOUT_S)  # type: ignore[union-attr]
        except queue.Empty:
            continue
        try:
            _run_review(sub_id)
        except Exception as exc:
            logger.warning('AI review of submission %d failed: %s', sub_id, exc)
        finally:
            try:
                _queue.task_done()  # type: ignore[union-attr]
            except Exception:
                pass


def _run_review(submission_id):
    """End-to-end review of one submission: call LLM, post comment, stamp.

    Returns the dict produced by ``contributions.add_comment`` so tests
    can assert against it directly. M2 will add bundle gathering before
    the LLM call; M3 will swap the stub ``_call_llm`` for the real one.
    """
    from . import contributions

    # Idempotency: a row that already has a stamp shouldn't be re-reviewed
    # automatically — re-runs go through the admin "Re-run AI review"
    # endpoint (M4), which clears the stamp first.
    sub = contributions.get_submission(submission_id, include_comments=False)
    if sub is None:
        logger.info('AI review skipped: submission %d not found', submission_id)
        return None
    if sub.get('last_ai_review_ts'):
        logger.info(
            'AI review skipped: submission %d already reviewed (idempotent)',
            submission_id,
        )
        return None

    t0 = time.monotonic()
    verdict = _call_llm(submission_id, _config.models[0] if _config else 'stub')
    verdict.latency_s = time.monotonic() - t0

    body = _render_comment_body(verdict)
    comment = contributions.add_comment(
        submission_id,
        author=None,
        author_role=contributions.ROLE_AI_REVIEWER,
        body=body,
    )
    contributions.mark_ai_review_completed(submission_id)
    logger.info(
        'AI review posted: submission=%d model=%s overall=%s findings=%d latency=%.2fs',
        submission_id, verdict.model, verdict.overall,
        len(verdict.findings), verdict.latency_s,
    )
    return comment


# ── stub LLM (M1) ───────────────────────────────────────────────────────────


def _call_llm(submission_id, model):
    """Stub returning a canned ``approve`` verdict.

    M1 stub. Tests monkey-patch this to drive specific scenarios; M3
    swaps in the real OpenAI-SDK-against-OpenRouter call. Signature is
    deliberately stable across milestones so the worker loop and tests
    don't need to change when the real implementation lands.
    """
    return _Verdict(
        overall='approve',
        confidence=0.85,
        summary=(
            'Stub verdict — M1 worker scaffolding. The real review will '
            'land once the OpenRouter call is wired in M3.'
        ),
        findings=[],
        model=model,
    )


# ── comment rendering ──────────────────────────────────────────────────────


def _render_comment_body(verdict):
    """Format a verdict as the Markdown body for an ai_reviewer comment.

    Capped confidence per ``AI_REVIEW_CONFIDENCE_CAP`` when set; privacy
    footer appended when ``AI_REVIEW_PRIVACY_NOTICE`` is non-empty. The
    M1 body is deliberately minimal — M4 adds severity sections,
    evidence breakdown, and the per-finding format.
    """
    cap = _config.confidence_cap if _config else 0.8
    rendered_conf = min(verdict.confidence, cap)
    capped_note = ' (capped)' if verdict.confidence > cap else ''

    lines = []
    lines.append(
        f'**AI review** · model=`{verdict.model}` · '
        f'overall=`{verdict.overall}` · '
        f'confidence={rendered_conf:.2f}{capped_note} · '
        f'{verdict.latency_s:.1f}s'
    )
    lines.append('')
    lines.append('## Summary')
    lines.append(verdict.summary)
    if verdict.findings:
        lines.append('')
        lines.append('## Findings')
        for f in verdict.findings:
            sev = f.get('severity', 'note')
            title = f.get('title', '(no title)')
            detail = f.get('detail', '')
            lines.append(f'- **{sev.upper()}** — {title}')
            if detail:
                lines.append(f'  > {detail}')
    else:
        lines.append('')
        lines.append('_No findings reported._')

    privacy = _config.privacy_notice if _config else ''
    if privacy:
        lines.append('')
        lines.append(f'_{privacy}_')
    return '\n'.join(lines)


# ── orphan scan ─────────────────────────────────────────────────────────────


def _scan_orphans():
    """Re-enqueue submissions whose AI review never completed.

    Runs once at the end of ``init_reviewer``. Cheap — single SQL
    ``SELECT id``. Safe if contributions isn't ready yet (e.g. tests
    that mock the module state); the call is wrapped in a broad except
    and logged.
    """
    if _disabled or _queue is None:
        return
    try:
        from . import contributions
        ids = contributions.list_orphaned_submission_ids()
    except Exception as exc:
        logger.info('AI orphan scan skipped: %s', exc)
        return
    for sub_id in ids:
        _queue.put(sub_id)
    if ids:
        logger.info('AI orphan scan: re-enqueued %d submission(s)', len(ids))
