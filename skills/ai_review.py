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

import json
import logging
import os
import queue
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

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

    M1/M2 used this as a plain dataclass over a stubbed verdict; M3
    keeps the dataclass for the in-memory passing but the *source* of
    its values is now Pydantic-validated (see ``_VerdictSchema`` below).
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
    # Only populated when JSON parsing / Pydantic validation failed at
    # every stage. Holds the raw model text (truncated) so the admin
    # can see what the model actually said.
    raw_text: Optional[str] = None
    # Synthesis tag used by the M3c chain wrapper. None when the model
    # legitimately returned this verdict (including a legitimate
    # ``needs_human_review`` recommendation); otherwise one of:
    #   'rate_limit'    — model said 429; cool-off bucket marked.
    #   'sdk_error'     — auth / connection / 5xx / timeout / etc.
    #   'parse_failure' — both initial + re-prompt attempts couldn't
    #                     produce a schema-valid response.
    error_type: Optional[str] = None


# Allowed enums for the LLM's reply. We tell the LLM about these in the
# system + user prompts; Pydantic enforces them at validation time.
_OVERALL_VALUES = ('approve', 'request_changes', 'reject', 'needs_human_review')
_SEVERITY_VALUES = ('block', 'warn', 'note')
_CATEGORY_VALUES = (
    'security', 'content', 'quality', 'duplicate',
    'policy', 'prompt_injection', 'licence',
)


class _Finding(BaseModel):
    """One finding inside the LLM verdict — Pydantic-validated."""
    severity: str = Field(...)
    category: str = Field(...)
    title: str = Field(default='(no title)', max_length=200)
    detail: str = Field(default='', max_length=2000)
    evidence: Optional[str] = Field(default=None, max_length=200)

    @classmethod
    def __get_validators__(cls):  # pragma: no cover — pydantic v2 internal
        yield from super().__get_validators__()

    def model_post_init(self, __context) -> None:  # pragma: no cover — coverage on the assert below
        if self.severity not in _SEVERITY_VALUES:
            raise ValueError(
                f'severity {self.severity!r} not in {_SEVERITY_VALUES!r}'
            )
        if self.category not in _CATEGORY_VALUES:
            raise ValueError(
                f'category {self.category!r} not in {_CATEGORY_VALUES!r}'
            )


class _VerdictSchema(BaseModel):
    """LLM reply contract. Validated before promotion to ``_Verdict``."""
    overall: str = Field(...)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    summary: str = Field(default='', max_length=3000)
    findings: list = Field(default_factory=list, max_length=20)
    checks_passed: list = Field(default_factory=list)

    def model_post_init(self, __context) -> None:
        if self.overall not in _OVERALL_VALUES:
            raise ValueError(
                f'overall {self.overall!r} not in {_OVERALL_VALUES!r}'
            )
        # Promote dicts → _Finding (validates inner enums); pass-through
        # if the caller already supplied _Finding instances.
        validated = []
        for f in self.findings:
            if isinstance(f, _Finding):
                validated.append(f)
            elif isinstance(f, dict):
                validated.append(_Finding(**f))
            else:
                raise ValueError(f'finding must be dict or _Finding, got {type(f).__name__}')
        # Cannot reassign attributes on a frozen model post-init, but we
        # can mutate the list in place (lists are not validated on assignment).
        self.findings.clear()
        self.findings.extend(validated)


# ── M2 prompt-composition constants ─────────────────────────────────────────

# Files we never try to read into the prompt — sending binary blobs to a text
# LLM is wasted tokens and may confuse the parser. Extensions only; binary
# files without an extension are filtered out by the null-byte probe below.
_BINARY_EXTS = frozenset({
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.bmp', '.tiff', '.svg',
    '.pdf', '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
    '.exe', '.dll', '.so', '.dylib', '.bin', '.dat',
    '.pyc', '.pyo', '.class', '.jar', '.o', '.a', '.lib',
    '.db', '.sqlite', '.sqlite3',
    '.woff', '.woff2', '.ttf', '.otf', '.eot',
    '.mp3', '.mp4', '.avi', '.mov', '.mkv', '.wav', '.flac', '.ogg', '.webm',
})

# File-tree, SKILL.md, and code-excerpt caps. Conservative defaults — M3 may
# tighten further once we have a real token meter, but for now char-counts
# at roughly 4 chars/token keep us comfortably inside AI_REVIEW_MAX_INPUT_TOKENS.
_MAX_FILE_TREE_ENTRIES = 64
_MAX_SKILL_MD_BYTES = 8 * 1024
_MAX_CODE_EXCERPT_TOTAL_BYTES = 16 * 1024
_MAX_PER_FILE_BYTES = 8 * 1024
_MAX_CATALOG_INDEX_ENTRIES = 60
_HASHES_DESC_PREFIX_CHARS = 80
# Code-bearing file extensions that get priority when we ration the
# _MAX_CODE_EXCERPT_TOTAL_BYTES budget. Python first because most submissions
# are Python skills.
_CODE_EXTS = ('.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.java',
              '.kt', '.swift', '.rb', '.php', '.sh', '.lua', '.c', '.h',
              '.cpp', '.hpp', '.cs')

_SYSTEM_PROMPT = """\
You are a code reviewer for an internal AI-skill marketplace.

You write findings; you do not approve, reject, or publish. The admin
makes the final call. Cite file paths and (when available) line numbers.
Never confabulate evidence — if you're not sure a path exists in the
bundle, omit that finding.

Severities:
  - block:  high-confidence security/policy violations
  - warn:   medium-confidence issues an admin should address
  - note:   low-priority polish

Output strict JSON matching the schema in the user message. The policy
this marketplace enforces is documented in docs/SKILL_POLICY.md; the
relevant rules are reproduced in the user prompt below.
"""

_RESPONSE_SCHEMA_HINT = """\
{
  "overall": "approve" | "request_changes" | "reject" | "needs_human_review",
  "confidence": 0.0,
  "summary": "one-paragraph executive summary for the admin",
  "findings": [
    {
      "severity": "block" | "warn" | "note",
      "category": "security" | "content" | "quality" | "duplicate" | "policy" | "prompt_injection" | "licence",
      "title": "short headline",
      "detail": "what you saw, why it matters",
      "evidence": "path/relative/from/bundle.py:42" | null
    }
  ],
  "checks_passed": ["short_check_id", ...]
}
"""


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
        global _rate_budget
        _rate_budget = _RateBudget(per_min=cfg.rate_budget_per_min)
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
    module-level reference (including the cached OpenAI client) so the
    next ``init_reviewer`` starts from a pristine state. Idempotent.
    """
    global _initialized, _disabled, _config, _queue, _workers, _client
    global _rate_budget
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
        _rate_budget = None
    with _client_lock:
        _client = None


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

    prompt = _compose_prompt(submission_id)
    bundle = _gather_bundle_context(submission_id)
    t0 = time.monotonic()
    models = list(_config.models) if _config and _config.models else ['stub']
    verdict = _call_llm_with_fallback(prompt, models)
    verdict.latency_s = time.monotonic() - t0
    # Strip findings the model invented file refs for (no-op when
    # disabled via AI_REVIEW_DROP_HALLUCINATED_EVIDENCE=false).
    verdict = _drop_hallucinated_evidence(verdict, bundle)

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

    # Auto-nudge from 'submitted' so the row lands in the admin's queue.
    # Other statuses (under_review, approved, rejected, published) are
    # left alone — the admin is already aware of those.
    if _should_nudge_to_under_review(verdict, sub.get('status')):
        try:
            contributions.update_status(
                submission_id,
                new_status=contributions.STATUS_UNDER_REVIEW,
                actor=None,
                actor_role=contributions.ROLE_SYSTEM,
                comment_body=None,
            )
            logger.info(
                'AI nudged submission %d → under_review (policy=%s)',
                submission_id, _config.auto_nudge if _config else 'always',
            )
        except Exception as exc:
            # update_status raises ContributionError on illegal transitions
            # — should never happen here (we already checked status), but
            # the worker keeps running even if it does.
            logger.warning(
                'AI nudge for submission %d failed: %s', submission_id, exc,
            )

    return comment


def _should_nudge_to_under_review(verdict, current_status) -> bool:
    """Decide whether an AI verdict should nudge the submission's status.

    Three policies driven by ``AI_REVIEW_AUTO_NUDGE``:

    * ``always`` (default) — every successful AI verdict on a
      ``submitted`` row bumps it to ``under_review``. Mostly noiseless
      because the chain wrapper synthesizes ``needs_human_review`` for
      total LLM failures, and those should still surface to an admin.
    * ``if_findings`` — only nudge when the verdict has at least one
      ``warn`` or ``block`` finding. Lets the admin's queue stay quiet
      for clean approves.
    * ``off`` — never nudge; admin runs the queue manually.

    Returns False for any current status other than ``submitted`` —
    the AI is a co-pilot, not a state-machine driver.
    """
    from . import contributions
    if current_status != contributions.STATUS_SUBMITTED:
        return False
    if not _config:
        return True
    policy = (_config.auto_nudge or 'always').lower()
    if policy == 'off':
        return False
    if policy == 'if_findings':
        return any(
            (f.get('severity') in ('warn', 'block'))
            for f in (verdict.findings or [])
        )
    # 'always' (and anything unknown).
    return True


# ── stub LLM (M1) ───────────────────────────────────────────────────────────


# ── tolerant JSON parser (M3) ──────────────────────────────────────────────


def _tolerant_json_load(raw):
    """Parse JSON out of an LLM response, tolerating common malformations.

    Four stages, returning as soon as one succeeds:

    1. ``json.loads(raw)`` strict.
    2. Strip a Markdown code fence (\\`\\`\\`json … \\`\\`\\` or generic
       fence) and try ``json.loads`` on the inner content.
    3. Regex-extract the *outermost* ``{ … }`` block (greedy, dot-all)
       and parse that.
    4. Give up — raise ``ValueError``.

    Free-tier models will sometimes wrap JSON in code fences or prepend
    a sentence of prose; stronger models almost never do. The 4-stage
    parser handles both without re-prompting on every call.
    """
    if raw is None:
        raise ValueError('empty response (None)')
    text = raw.strip()
    if not text:
        raise ValueError('empty response (whitespace)')

    # Stage 1 — strict.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Stage 2 — strip a fenced code block (```json … ``` or ``` … ```).
    fence_match = re.search(
        r'```(?:json|JSON)?\s*\n?(.*?)\n?```',
        text,
        re.DOTALL,
    )
    if fence_match:
        inner = fence_match.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            pass

    # Stage 3 — extract the *outermost* { … } block. Greedy `.*` with
    # DOTALL grabs from the first `{` to the last `}`, which works for
    # any single-JSON-object payload (LLMs don't return multiple top-level
    # objects when asked for one).
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError('no parseable JSON in response')


# ── LLM call (M3) ──────────────────────────────────────────────────────────


_client_lock = threading.Lock()
_client = None    # cached OpenAI client; rebuilt on _reset_for_tests


# Cool-off window after a 429 from an upstream. 30 s matches OpenRouter's
# typical reset for free-tier rate-limit responses; tightening below 20 s
# tends to re-trip the limit immediately.
_COOLOFF_SECONDS = 30


class _RateBudget:
    """Per-model sliding-window counter + cool-off bucket.

    Thread-safe. Two responsibilities:

    * ``take(model)`` — best-effort local rate limit. Returns False if
      this model has already hit ``per_min`` calls in the trailing
      60 seconds, otherwise records the call and returns True. The cap
      is ``per_min``; 0 disables the budget (always True).
    * ``record_429(model)`` + ``is_cooled(model)`` — when an upstream
      ``429`` slips past the local budget (or the local budget was
      disabled), mark this model as cooled for ``_COOLOFF_SECONDS``.
      ``is_cooled`` is honoured by the chain wrapper.

    State is intentionally per-process and ephemeral. The chain wrapper
    walks past any cooled model and a fresh process restart starts
    everyone uncooled — the trade-off is that a crash-loop won't
    inherit a meaningful budget, but it also won't get stuck in cool-off
    forever.
    """

    def __init__(self, per_min: int = 15, cooloff_seconds: int = _COOLOFF_SECONDS):
        self._per_min = max(int(per_min), 0)
        self._cooloff_s = cooloff_seconds
        self._lock = threading.Lock()
        self._calls: dict = {}        # model → list[monotonic ts]
        self._cool_until: dict = {}   # model → monotonic ts when cooled

    def take(self, model: str) -> bool:
        if self._per_min <= 0:
            return True
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            calls = [t for t in self._calls.get(model, []) if t > cutoff]
            if len(calls) >= self._per_min:
                self._calls[model] = calls
                return False
            calls.append(now)
            self._calls[model] = calls
            return True

    def is_cooled(self, model: str) -> bool:
        with self._lock:
            until = self._cool_until.get(model, 0.0)
            return time.monotonic() < until

    def record_429(self, model: str) -> None:
        with self._lock:
            self._cool_until[model] = time.monotonic() + self._cooloff_s


_rate_budget: Optional[_RateBudget] = None    # initialised in init_reviewer


def _get_client():
    """Build (and memoise) the OpenAI-compatible client.

    The SDK is import-only when first used so a config with no API key
    pays nothing at boot. Re-uses one client across worker threads —
    httpx's connection pool inside the SDK handles concurrency.
    """
    global _client
    with _client_lock:
        if _client is not None:
            return _client
        from openai import OpenAI
        _client = OpenAI(
            base_url=_config.base_url,
            api_key=_config.api_key,
            default_headers=_config.extra_headers or None,
            timeout=_config.timeout_s,
        )
        return _client


def _stub_verdict(prompt, model):
    """Canned ``approve`` verdict used when no LLM API key is configured.

    Preserves the M0–M2 test behaviour: tests can drive the full worker
    flow with ``LLM_API_KEY=''`` (or omitted) without making a network
    call. Production never hits this path because operators flip
    ``AI_REVIEW_ENABLED=true`` *after* setting an API key.
    """
    return _Verdict(
        overall='approve',
        confidence=0.85,
        summary=(
            f'Stub verdict — LLM_API_KEY not configured. Prompt was '
            f'composed ({len(prompt)} chars). Set LLM_API_KEY (or '
            f'OPENROUTER_API_KEY) in env to run real reviews.'
        ),
        findings=[],
        model=model,
    )


def _llm_chat_completion(model, messages):
    """Single chat-completion call. Returns ``(raw_text, error_or_None)``.

    Catches every SDK-level exception (auth, connection, 4xx/5xx, etc.)
    and converts to a ``(None, exc)`` tuple so the caller can fall
    through to ``needs_human_review`` instead of crashing the worker.
    """
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={'type': 'json_object'},
            temperature=0.1,
            max_tokens=1500,
        )
        return response.choices[0].message.content, None
    except Exception as exc:    # noqa: BLE001 — defensive boundary
        logger.warning('LLM call failed (model=%s): %s', model, exc)
        return None, exc


def _classify_sdk_error(exc) -> str:
    """Map an openai SDK exception to a short ``error_type`` tag.

    Used by the chain wrapper to decide whether to cool-off a model
    (``rate_limit``) vs. just walk to the next one (``sdk_error``).
    """
    try:
        import openai
    except ImportError:
        return 'sdk_error'
    rate_limit_cls = getattr(openai, 'RateLimitError', None)
    if rate_limit_cls is not None and isinstance(exc, rate_limit_cls):
        return 'rate_limit'
    # Some OpenRouter free-tier providers report 429 as a plain
    # APIStatusError with status_code=429 rather than RateLimitError.
    status = getattr(exc, 'status_code', None) or getattr(exc, 'http_status', None)
    if status == 429:
        return 'rate_limit'
    return 'sdk_error'


def _parse_or_validation_fail(raw, model):
    """Turn raw LLM text into a validated ``_VerdictSchema`` or ``None``."""
    if raw is None:
        return None
    try:
        obj = _tolerant_json_load(raw)
    except ValueError as exc:
        logger.info('LLM verdict JSON parse failed (model=%s): %s', model, exc)
        return None
    try:
        return _VerdictSchema(**obj)
    except (ValidationError, ValueError) as exc:
        logger.info(
            'LLM verdict Pydantic validation failed (model=%s): %s',
            model, exc,
        )
        return None


def _verdict_from_schema(schema, model):
    """Promote a validated ``_VerdictSchema`` into a ``_Verdict``."""
    return _Verdict(
        overall=schema.overall,
        confidence=schema.confidence,
        summary=schema.summary,
        findings=[
            f.model_dump() if isinstance(f, _Finding) else dict(f)
            for f in schema.findings
        ],
        model=model,
    )


def _call_llm(prompt, model):
    """Get one verdict from one model.

    Per-model boundary used by ``_call_llm_with_fallback``. The chain
    wrapper handles model rotation, cool-off, and rate budget; this
    function handles only the request → parse → validate → reprompt
    cycle for a single model.

    Branches on whether ``LLM_API_KEY`` is configured:

    * No key → ``_stub_verdict`` (lets M0–M2 tests keep working without
      a network).
    * Key set → real ``chat.completions.create``. Tolerant JSON parse +
      Pydantic validate; one re-prompt with an explicit JSON-only
      instruction on first parse/validation failure; ``needs_human_review``
      with ``error_type`` set on:

        * SDK exception (e.g. 429, 5xx, timeout, auth) → tagged with
          ``rate_limit`` or ``sdk_error`` so the chain can decide.
        * Both attempts produced unparseable output →
          ``error_type='parse_failure'``, ``raw_text`` populated.

    A successful verdict has ``error_type=None``.
    """
    if not _config or not _config.api_key:
        return _stub_verdict(prompt, model)

    messages = [
        {'role': 'system', 'content': _SYSTEM_PROMPT},
        {'role': 'user', 'content': prompt},
    ]

    # First attempt.
    raw, exc = _llm_chat_completion(model, messages)
    if exc is not None:
        return _sdk_error_verdict(exc, model)
    schema = _parse_or_validation_fail(raw, model)
    if schema is not None:
        return _verdict_from_schema(schema, model)

    # Single re-prompt with an explicit JSON-only kicker. Free models
    # sometimes ignore response_format on the first call but comply on
    # the retry because the instruction is right next to the schema.
    retry_messages = [
        {'role': 'system', 'content': _SYSTEM_PROMPT},
        {'role': 'user', 'content': (
            prompt
            + '\n\n## IMPORTANT\n'
            + 'Reply with valid JSON only matching the schema above. '
            + 'No prose, no Markdown code fences, no commentary.'
        )},
    ]
    raw2, exc2 = _llm_chat_completion(model, retry_messages)
    if exc2 is not None:
        return _sdk_error_verdict(exc2, model)
    schema2 = _parse_or_validation_fail(raw2, model)
    if schema2 is not None:
        return _verdict_from_schema(schema2, model)

    # Both attempts produced unparseable output. Surface the raw text
    # (truncated) and tag for the chain wrapper.
    raw_for_admin = raw2 or raw
    if raw_for_admin and len(raw_for_admin) > 2000:
        raw_for_admin = raw_for_admin[:2000] + '\n…(truncated)'
    return _Verdict(
        overall='needs_human_review',
        confidence=0.0,
        summary=(
            'AI verdict unavailable — the model response could not be '
            'parsed as the required JSON schema after one re-prompt. '
            'Admin should review manually.'
        ),
        findings=[],
        model=model,
        raw_text=raw_for_admin,
        error_type='parse_failure',
    )


def _sdk_error_verdict(exc, model) -> _Verdict:
    """Build a needs_human_review verdict tagged with the SDK error kind."""
    kind = _classify_sdk_error(exc)
    summary = (
        'Rate-limited by the LLM provider.'
        if kind == 'rate_limit'
        else f'LLM call failed: {type(exc).__name__}: {str(exc)[:200]}'
    )
    return _Verdict(
        overall='needs_human_review',
        confidence=0.0,
        summary=summary,
        findings=[],
        model=model,
        raw_text=None,
        error_type=kind,
    )


def _call_llm_with_fallback(prompt, models):
    """Walk ``models`` in order, returning the first non-error verdict.

    For each model:

    1. Skip if currently cooled (``_rate_budget.is_cooled``).
    2. Skip if local rate budget exhausted (``_rate_budget.take``).
    3. Call ``_call_llm(prompt, model)``.
    4. If ``error_type == 'rate_limit'``: record cool-off, continue.
    5. If ``error_type in ('sdk_error', 'parse_failure')``: continue.
    6. Otherwise return the verdict — including a legitimate
       ``needs_human_review`` from the model (``error_type=None``).

    If every model is exhausted/cooled/erroring, return a synthesized
    ``needs_human_review`` whose ``summary`` explains why and whose
    ``raw_text`` carries the last raw model output (if any).
    """
    if not models:
        return _Verdict(
            overall='needs_human_review',
            confidence=0.0,
            summary='AI reviewer has no models configured.',
            findings=[],
            model='',
            error_type='sdk_error',
        )

    last_verdict: Optional[_Verdict] = None
    tried_any = False

    for model in models:
        if _rate_budget is not None and _rate_budget.is_cooled(model):
            logger.info('chain: skipping %s (cool-off)', model)
            continue
        if _rate_budget is not None and not _rate_budget.take(model):
            logger.info('chain: skipping %s (rate budget exhausted)', model)
            continue

        tried_any = True
        verdict = _call_llm(prompt, model)
        last_verdict = verdict

        if verdict.error_type is None:
            return verdict
        if verdict.error_type == 'rate_limit' and _rate_budget is not None:
            _rate_budget.record_429(model)

        # Walk to the next model.
        logger.info(
            'chain: %s failed with %s, walking to next',
            model, verdict.error_type,
        )

    # Chain exhausted.
    if last_verdict is not None:
        return _Verdict(
            overall='needs_human_review',
            confidence=0.0,
            summary=(
                'AI reviewer exhausted the configured model chain '
                f'({len(models)} model{"s" if len(models) != 1 else ""}). '
                f'Last failure: {last_verdict.error_type}. '
                'Admin should review manually.'
            ),
            findings=[],
            model=last_verdict.model,
            raw_text=last_verdict.raw_text,
            error_type=last_verdict.error_type,
        )
    if not tried_any:
        return _Verdict(
            overall='needs_human_review',
            confidence=0.0,
            summary=(
                'AI reviewer skipped all models: every one was either '
                'cooled or rate-budget-exhausted.'
            ),
            findings=[],
            model=models[0],
            error_type='rate_limit',
        )
    return _Verdict(
        overall='needs_human_review',
        confidence=0.0,
        summary='AI reviewer exhausted model chain with no usable verdict.',
        findings=[],
        model=models[0],
        error_type='sdk_error',
    )


# ── hallucinated-evidence drop (M3c) ───────────────────────────────────────


def _drop_hallucinated_evidence(verdict, bundle):
    """Strip findings whose ``evidence`` cites a path absent from the bundle.

    Free-tier models occasionally invent file paths to support a
    finding (e.g. "creds in `secrets.py:42`" when there is no
    `secrets.py`). When ``AI_REVIEW_DROP_HALLUCINATED_EVIDENCE=true``
    (default), drop those findings before they reach the admin.
    Findings with ``evidence=None`` are always kept — the model didn't
    cite anything to hallucinate.

    Mutates and returns ``verdict``.
    """
    if not _config or not _config.drop_hallucinated_evidence:
        return verdict
    if not verdict.findings:
        return verdict
    # An empty / missing bundle is *not* a reason to skip the pass —
    # findings citing paths must still be dropped because no path could
    # legitimately be in an empty bundle. The early-return below catches
    # only the "bundle is None" case (gather function isn't supposed to
    # return None, but be defensive).
    if bundle is None:
        return verdict

    # Build the set of known relPaths from the bundle. We accept either
    # exact match (the model cited the same relPath we sent it) or a
    # path that is a *suffix* of a known relPath (the model truncated
    # the leading folders).
    known = set()
    for entry in bundle.get('file_tree') or []:
        rel = entry.get('relPath')
        if rel:
            known.add(rel)
    for entry in bundle.get('code_excerpts') or []:
        rel = entry.get('relPath')
        if rel:
            known.add(rel)

    def _path_known(evidence: str) -> bool:
        # Evidence format: "path/relative.py:42" or "path/relative.py".
        path = evidence.split(':', 1)[0].strip()
        if not path:
            return False
        if path in known:
            return True
        return any(k == path or k.endswith('/' + path) for k in known)

    kept = []
    dropped = 0
    for f in verdict.findings:
        evidence = f.get('evidence')
        if evidence is None:
            kept.append(f)
            continue
        if _path_known(evidence):
            kept.append(f)
        else:
            dropped += 1

    if dropped:
        logger.info(
            'dropped %d finding(s) citing paths absent from the bundle '
            '(submission verdict)', dropped,
        )
    verdict.findings = kept
    return verdict


# ── bundle context gathering (M2) ──────────────────────────────────────────


def _read_text_safely(path, max_bytes):
    """Read up to ``max_bytes`` of a file as UTF-8/Latin-1 text.

    Returns ``(text, truncated)`` on success or ``None`` if the file is
    binary (null byte in the sniffed prefix) or unreadable. The two
    decodings cover the realistic dev-tool universe; further encoding
    detection would be over-engineering for a code reviewer's eyeballs.
    """
    try:
        with open(path, 'rb') as f:
            raw = f.read(max_bytes + 1)
    except OSError:
        return None
    truncated = len(raw) > max_bytes
    if truncated:
        raw = raw[:max_bytes]
    if b'\x00' in raw:
        return None
    try:
        return raw.decode('utf-8'), truncated
    except UnicodeDecodeError:
        try:
            return raw.decode('latin-1'), truncated
        except Exception:
            return None


def _gather_bundle_context(submission_id):
    """Pull the per-submission context the AI needs to review.

    Returns a dict with three keys:

    * ``skill_md`` — string (first ``_MAX_SKILL_MD_BYTES`` of SKILL.md, or
      empty when missing).
    * ``file_tree`` — list of ``{'relPath', 'size'}`` entries, capped at
      ``_MAX_FILE_TREE_ENTRIES``. SKILL.md sorted first; rest by
      ``relPath`` (matches ``contributions.list_extracted_files``).
    * ``code_excerpts`` — list of ``{'relPath', 'content', 'truncated'}``
      capped at ``_MAX_CODE_EXCERPT_TOTAL_BYTES`` total, prioritising
      ``_CODE_EXTS`` and dropping binary extensions outright.

    Tolerates missing/disabled contributions storage — returns empty
    structures rather than raising, so the worker can still produce a
    minimal verdict.
    """
    out = {'skill_md': '', 'file_tree': [], 'code_excerpts': []}
    try:
        from . import contributions
        files = contributions.list_extracted_files(submission_id)
        blob_dir = getattr(contributions, '_blob_dir', None)
    except Exception as exc:
        logger.info('bundle gather skipped: %s', exc)
        return out
    if not files or not blob_dir:
        return out

    extract_root = os.path.join(blob_dir, str(submission_id), 'extracted')

    # ── file tree (capped) ────────────────────────────────────────────
    out['file_tree'] = [
        {'relPath': f['relPath'], 'size': f['size']}
        for f in files[:_MAX_FILE_TREE_ENTRIES]
    ]
    if len(files) > _MAX_FILE_TREE_ENTRIES:
        out['file_tree'].append({
            'relPath': f'... ({len(files) - _MAX_FILE_TREE_ENTRIES} more files truncated) ...',
            'size': 0,
        })

    # ── SKILL.md content ──────────────────────────────────────────────
    for f in files:
        if f['name'] == 'SKILL.md':
            result = _read_text_safely(
                os.path.join(extract_root, f['relPath']), _MAX_SKILL_MD_BYTES,
            )
            if result is not None:
                out['skill_md'] = result[0]
            break

    # ── code excerpts (priority by extension, then size) ──────────────
    def _ext_priority(rel):
        ext = os.path.splitext(rel)[1].lower()
        if ext in _CODE_EXTS:
            return _CODE_EXTS.index(ext)
        return len(_CODE_EXTS)  # text but non-code → after all code files

    candidates = []
    for f in files:
        rel = f['relPath']
        if rel.endswith('SKILL.md'):
            continue   # already included separately
        ext = os.path.splitext(rel)[1].lower()
        if ext in _BINARY_EXTS:
            continue
        candidates.append(f)

    candidates.sort(key=lambda f: (_ext_priority(f['relPath']), -int(f['size'] or 0)))

    used_bytes = 0
    for f in candidates:
        if used_bytes >= _MAX_CODE_EXCERPT_TOTAL_BYTES:
            break
        budget = _MAX_CODE_EXCERPT_TOTAL_BYTES - used_bytes
        per_file = min(_MAX_PER_FILE_BYTES, budget)
        result = _read_text_safely(
            os.path.join(extract_root, f['relPath']), per_file,
        )
        if result is None:
            continue
        text, truncated = result
        out['code_excerpts'].append({
            'relPath': f['relPath'],
            'content': text,
            'truncated': truncated,
        })
        used_bytes += len(text)

    return out


def _catalog_index():
    """Snapshot the live catalog for duplicate-detection in the prompt.

    Returns a list of ``{'slug', 'name', 'desc'}`` entries, capped at
    ``_MAX_CATALOG_INDEX_ENTRIES`` and ordered by ``lastUpdated``
    desc. ``desc`` is the first ``_HASHES_DESC_PREFIX_CHARS`` characters
    of each skill's description in ``hashes`` mode (the OpenRouter
    privacy default), or the full description in ``full`` mode (intended
    for internal endpoints where leakage is not a concern).
    """
    try:
        from . import watcher
        skills_map = watcher.get_skills()
    except Exception as exc:
        logger.info('catalog snapshot skipped: %s', exc)
        return []

    detail = (_config.catalog_detail if _config else 'hashes').lower()

    entries = []
    for slug, skill in skills_map.items():
        entries.append({
            'slug': slug,
            'name': skill.get('name') or slug,
            'desc': skill.get('description') or '',
            'lastUpdated': skill.get('lastUpdated') or 0,
        })
    entries.sort(key=lambda e: e['lastUpdated'] or 0, reverse=True)

    truncated_count = max(0, len(entries) - _MAX_CATALOG_INDEX_ENTRIES)
    entries = entries[:_MAX_CATALOG_INDEX_ENTRIES]

    out = []
    for e in entries:
        desc = e['desc']
        if detail == 'hashes':
            desc = desc[:_HASHES_DESC_PREFIX_CHARS]
            if len(e['desc']) > _HASHES_DESC_PREFIX_CHARS:
                desc = desc.rstrip() + '…'
        out.append({'slug': e['slug'], 'name': e['name'], 'desc': desc})
    if truncated_count:
        out.append({
            'slug': '__truncated__',
            'name': f'(+{truncated_count} more)',
            'desc': 'catalog partial — older entries omitted',
        })
    return out


def _compose_prompt(submission_id):
    """Assemble the user-message body for one review.

    Sections (in order, separated by blank lines):

    1. **Submission metadata** — submission id, slug, title, license,
       file size. Submitter cookie name + IP + original filename are
       **never** included (defence-in-depth privacy boundary).
    2. **SKILL.md** — first ``_MAX_SKILL_MD_BYTES`` of the bundle's
       SKILL.md content, fenced.
    3. **File tree** — ``relPath`` and size, ≤ ``_MAX_FILE_TREE_ENTRIES``.
    4. **Code excerpts** — text-mode contents of priority files, ≤
       ``_MAX_CODE_EXCERPT_TOTAL_BYTES`` total.
    5. **Existing catalog** — slug + name + description (full or
       prefix depending on ``AI_REVIEW_CATALOG_DETAIL``).
    6. **Policy** — cite ``docs/SKILL_POLICY.md`` so the LLM follows
       the same rules the admin does.
    7. **Output schema** — the JSON shape the LLM must reply with.

    The final string is then truncated to ``AI_REVIEW_MAX_INPUT_TOKENS``
    estimated as ``max_input_tokens * 4`` chars (rough OpenAI heuristic;
    M3 may swap a real tokenizer).
    """
    # Submission metadata — fetched here rather than getting passed in so
    # the function is callable from tests with just an id.
    sub = None
    try:
        from . import contributions
        sub = contributions.get_submission(submission_id, include_comments=False)
    except Exception as exc:
        logger.info('compose_prompt metadata fetch skipped: %s', exc)

    bundle = _gather_bundle_context(submission_id)
    catalog = _catalog_index()

    lines = []
    lines.append('## Submission')
    if sub:
        lines.append(f'- id: {sub["id"]}')
        lines.append(f'- slug: `{sub["slug"]}`')
        lines.append(f'- title: {sub["title"]}')
        lines.append(f'- license: {sub.get("license") or "(unspecified)"}')
        lines.append(f'- file size: {sub.get("fileSize") or 0} bytes')
    else:
        lines.append(f'- id: {submission_id}')
        lines.append('- (metadata unavailable)')

    lines.append('')
    lines.append('## SKILL.md')
    if bundle['skill_md']:
        lines.append('```markdown')
        lines.append(bundle['skill_md'])
        lines.append('```')
    else:
        lines.append('_SKILL.md not readable — fall back to file-tree heuristics._')

    lines.append('')
    lines.append('## Bundle file tree')
    if bundle['file_tree']:
        for entry in bundle['file_tree']:
            lines.append(f'- `{entry["relPath"]}` ({entry["size"]} bytes)')
    else:
        lines.append('_(empty)_')

    lines.append('')
    lines.append('## Code excerpts')
    if bundle['code_excerpts']:
        for ex in bundle['code_excerpts']:
            tnote = ' (truncated)' if ex['truncated'] else ''
            lines.append(f'### `{ex["relPath"]}`{tnote}')
            lines.append('```')
            lines.append(ex['content'])
            lines.append('```')
    else:
        lines.append('_(no readable code files)_')

    lines.append('')
    lines.append('## Existing catalog (for duplicate detection)')
    if catalog:
        for entry in catalog:
            lines.append(f'- `{entry["slug"]}` — **{entry["name"]}** — {entry["desc"]}')
    else:
        lines.append('_(catalog snapshot unavailable)_')

    lines.append('')
    lines.append('## Policy')
    lines.append(
        'Apply the rules in `docs/SKILL_POLICY.md`: allowed licenses are '
        'MIT / Apache-2.0 / BSD / ISC / Unlicense / 0BSD / CC0-1.0. '
        'Unknown licenses are `warn`, never `block`. Hardcoded credentials, '
        'prompt-injection patterns, and high-confidence policy violations '
        'are `block`. Polish issues are `note`. The admin owns the final '
        'decision — your verdict is advisory.'
    )

    lines.append('')
    lines.append('## Output schema')
    lines.append('```json')
    lines.append(_RESPONSE_SCHEMA_HINT.rstrip())
    lines.append('```')

    body = '\n'.join(lines)

    # Char-based truncation as a coarse stand-in for tokenisation. 4 chars
    # per token is the OpenAI English-text heuristic. M3 may swap in a real
    # tokenizer once the prompt format settles.
    max_chars = (_config.max_input_tokens if _config else 12000) * 4
    if len(body) > max_chars:
        body = body[:max_chars] + '\n\n…(prompt truncated to max_input_tokens budget)'

    return body


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

    # Raw model text only present when JSON parsing/validation failed
    # at every stage — surface it so the admin can sanity-check what the
    # model actually said (truncated to 2 KB by ``_call_llm``).
    if verdict.raw_text:
        lines.append('')
        lines.append('## Raw model response (parse failed)')
        lines.append('```')
        lines.append(verdict.raw_text)
        lines.append('```')

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
