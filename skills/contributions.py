"""User-contributed skill submissions.

Flow (phase 1):
    submitter uploads ZIP
        → submission row created with status='submitted'
    admin views queue, leaves comments, moves status
        submitted → under_review → approved | changes_requested | rejected
    admin clicks Publish (only on status='approved')
        → ZIP contents copied into SKILL_REPO_PATH, status='published',
          file watcher picks the new skill up live.

Phase 2 (not implemented here, but the data model supports it):
    AI reviewer adds an `ai_reviewer`-role comment automatically; the
    submitter — not the admin — clicks Publish on approved submissions.

Storage:
    SQLite at SUBMISSIONS_DB_PATH (separate from the usage DB) and a
    per-submission blob directory at SUBMISSIONS_BLOB_DIR/<id>/. The
    original ZIP is kept verbatim so a reviewer can re-download what
    was submitted, and an extracted/ subdirectory holds the unpacked
    contents that the admin sees a tree of in the UI.

This module never raises into request handlers except as
`ContributionError(message, http_status)` — views catch that and map
straight to a JSON response.
"""

from __future__ import annotations

import io
import logging
import os
import re
import shutil
import sqlite3
import threading
import time
import zipfile
from dataclasses import dataclass

import frontmatter

logger = logging.getLogger('skills.contributions')


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

STATUS_SUBMITTED = 'submitted'
STATUS_UNDER_REVIEW = 'under_review'
STATUS_CHANGES_REQUESTED = 'changes_requested'
STATUS_APPROVED = 'approved'
STATUS_REJECTED = 'rejected'
STATUS_PUBLISHED = 'published'

ALL_STATUSES = (
    STATUS_SUBMITTED,
    STATUS_UNDER_REVIEW,
    STATUS_CHANGES_REQUESTED,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_PUBLISHED,
)

# Legal forward transitions. A few backward moves (e.g. approved → under_review)
# are intentionally allowed so an admin can yank approval before publishing.
_LEGAL_TRANSITIONS: dict[str, set[str]] = {
    STATUS_SUBMITTED: {STATUS_UNDER_REVIEW, STATUS_REJECTED, STATUS_CHANGES_REQUESTED},
    STATUS_UNDER_REVIEW: {
        STATUS_APPROVED, STATUS_CHANGES_REQUESTED, STATUS_REJECTED,
    },
    STATUS_CHANGES_REQUESTED: {STATUS_UNDER_REVIEW, STATUS_REJECTED},
    STATUS_APPROVED: {STATUS_UNDER_REVIEW, STATUS_REJECTED, STATUS_PUBLISHED},
    STATUS_REJECTED: {STATUS_UNDER_REVIEW},   # revive a wrongly-rejected entry
    STATUS_PUBLISHED: set(),                  # terminal
}


ROLE_SUBMITTER = 'submitter'
ROLE_ADMIN = 'admin'
ROLE_AI_REVIEWER = 'ai_reviewer'   # phase-2 placeholder; permitted in schema today
ROLE_SYSTEM = 'system'             # state-change audit trail

ALL_ROLES = (ROLE_SUBMITTER, ROLE_ADMIN, ROLE_AI_REVIEWER, ROLE_SYSTEM)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ContributionError(Exception):
    """Domain error mapped straight onto an HTTP response by views."""

    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.http_status = http_status


# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()
_initialized = False
_disabled = False
_db_path: str | None = None
_blob_dir: str | None = None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  slug                  TEXT    NOT NULL,
  title                 TEXT    NOT NULL,
  description           TEXT,
  license               TEXT,
  submitter             TEXT,
  submitter_ip          TEXT,
  status                TEXT    NOT NULL,
  file_path             TEXT    NOT NULL,
  file_size             INTEGER NOT NULL,
  original_filename     TEXT,
  created_ts            REAL    NOT NULL,
  updated_ts            REAL    NOT NULL,
  published_skill_dir   TEXT,
  last_ai_review_ts     REAL
);
CREATE INDEX IF NOT EXISTS idx_subs_status_updated ON submissions(status, updated_ts DESC);
CREATE INDEX IF NOT EXISTS idx_subs_submitter      ON submissions(submitter);
CREATE INDEX IF NOT EXISTS idx_subs_last_ai_review ON submissions(last_ai_review_ts);

CREATE TABLE IF NOT EXISTS submission_comments (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  author        TEXT,
  author_role   TEXT NOT NULL,
  body          TEXT NOT NULL,
  created_ts    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_sub ON submission_comments(submission_id, created_ts ASC);
"""


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def init_submissions(db_path: str, blob_dir: str) -> bool:
    """Open the submissions DB and ensure the blob directory exists.

    Idempotent; safe to call from `apps.SkillsConfig.ready` lazy init.
    Returns True on success, False if storage couldn't be opened.
    """
    global _conn, _initialized, _disabled, _db_path, _blob_dir

    with _lock:
        if _initialized:
            return not _disabled
        _initialized = True
        _db_path = db_path
        _blob_dir = blob_dir

        try:
            parent = os.path.dirname(db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            os.makedirs(blob_dir, exist_ok=True)
            _conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
            _conn.execute('PRAGMA journal_mode=WAL')
            _conn.execute('PRAGMA synchronous=NORMAL')
            _conn.execute('PRAGMA busy_timeout=2000')
            _conn.execute('PRAGMA foreign_keys=ON')
            _conn.executescript(_SCHEMA)
            _ensure_last_ai_review_ts_column(_conn)
        except Exception as exc:
            _disabled = True
            _conn = None
            logger.error(
                'submissions DB init failed (%s): %s — contributions disabled',
                db_path, exc,
            )
            return False

    logger.info('submissions DB ready (%s, blob_dir=%s)', db_path, blob_dir)
    return True


def _require_ready():
    if _disabled or _conn is None or _blob_dir is None:
        raise ContributionError('contributions storage unavailable', http_status=503)


def _ensure_last_ai_review_ts_column(conn: sqlite3.Connection) -> None:
    """Add the last_ai_review_ts column to pre-existing submission tables.

    SQLite has no IF NOT EXISTS on ALTER TABLE; we treat 'duplicate column'
    as success so upgrades stay idempotent. Mirrors usage._ensure_ip_column.
    """
    try:
        conn.execute('ALTER TABLE submissions ADD COLUMN last_ai_review_ts REAL')
    except sqlite3.OperationalError as exc:
        if 'duplicate column' not in str(exc).lower():
            raise


# ---------------------------------------------------------------------------
# AI-reviewer integration helpers
# ---------------------------------------------------------------------------
#
# These are tiny query/UPDATE helpers used by skills.ai_review so it never
# has to open its own connection to this DB. Keeping the boundary here means
# the ai_review module stays self-contained and the contributions schema
# stays the single source of truth.


def list_orphaned_submission_ids() -> list[int]:
    """IDs of submissions that need (or need re-asking-for) an AI review.

    Returns submissions whose ``last_ai_review_ts`` is NULL and whose
    ``status`` is still in flight (``submitted`` or ``under_review``).
    The AI reviewer uses this on startup to recover work that was queued
    but not finished before the previous process restart.
    """
    _require_ready()
    with _lock:
        rows = _conn.execute(  # type: ignore[union-attr]
            "SELECT id FROM submissions "
            "WHERE last_ai_review_ts IS NULL "
            "  AND status IN (?, ?) "
            "ORDER BY created_ts ASC",
            (STATUS_SUBMITTED, STATUS_UNDER_REVIEW),
        ).fetchall()
    return [r[0] for r in rows]


def mark_ai_review_completed(submission_id: int) -> None:
    """Stamp ``last_ai_review_ts`` so the orphan scan won't re-pick this row.

    Idempotent — a row that's already been stamped just gets a fresher ts.
    """
    _require_ready()
    now = time.time()
    with _lock:
        _conn.execute(  # type: ignore[union-attr]
            'UPDATE submissions SET last_ai_review_ts = ? WHERE id = ?',
            (now, submission_id),
        )


# Stable marker prefix used by the AI re-run audit comment. The marker
# is also recognised by ``count_recent_ai_reruns`` so the worker can
# enforce a per-submission daily quota without a dedicated counter
# table. Cf. ``api_contribution_rerun_ai`` in skills/views.py.
AI_RERUN_MARKER = 'AI review re-run requested'


def clear_ai_review_stamp(submission_id: int) -> None:
    """Reset ``last_ai_review_ts`` to NULL.

    Used by the M4 "Re-run AI review" admin button so the worker thread
    doesn't short-circuit the next review with the idempotency guard.
    """
    _require_ready()
    with _lock:
        _conn.execute(  # type: ignore[union-attr]
            'UPDATE submissions SET last_ai_review_ts = NULL WHERE id = ?',
            (submission_id,),
        )


def count_recent_ai_reruns(submission_id: int, within_seconds: int = 86400) -> int:
    """How many AI re-runs of this submission happened in the last window.

    Used by the rerun endpoint to enforce
    ``AI_REVIEW_RERUN_DAILY_CAP_PER_SUBMISSION``. Counts system comments
    whose body starts with the stable marker prefix
    ``AI_RERUN_MARKER`` so no new schema column is needed.

    A ``within_seconds`` of 86400 = the rolling last 24 hours.
    """
    _require_ready()
    cutoff = time.time() - max(int(within_seconds), 1)
    with _lock:
        row = _conn.execute(  # type: ignore[union-attr]
            'SELECT COUNT(*) FROM submission_comments '
            'WHERE submission_id = ? '
            '  AND author_role = ? '
            "  AND body LIKE ? "
            '  AND created_ts >= ?',
            (submission_id, ROLE_SYSTEM, f'{AI_RERUN_MARKER}%', cutoff),
        ).fetchone()
    return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

# Same shape as the skill_repo layout: kebab-ish, ASCII, no surprises.
_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._\- ]{0,127}$')


def _slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r'[^a-z0-9._-]+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s[:63] or 'skill'


def _unique_slug(base: str) -> str:
    """Return a slug not yet taken by any submission (any status)."""
    assert _conn is not None
    candidate = base
    suffix = 1
    while True:
        row = _conn.execute(
            'SELECT 1 FROM submissions WHERE slug = ? LIMIT 1', (candidate,)
        ).fetchone()
        if not row:
            return candidate
        suffix += 1
        candidate = f'{base}-{suffix}'[:63]


def _safe_extract(zip_bytes: bytes, dest_dir: str, max_uncompressed: int) -> None:
    """Extract a ZIP while refusing path traversal and quota-busting blobs.

    - Rejects entries with absolute paths, `..` segments, or symlink members.
    - Caps total uncompressed size (zip-bomb defence).
    """
    total = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # Detect zip bombs before any write.
        for info in zf.infolist():
            if info.file_size < 0:
                raise ContributionError('zip member has invalid size')
            total += info.file_size
            if total > max_uncompressed:
                raise ContributionError(
                    f'extracted size {total} exceeds limit {max_uncompressed}',
                )
            name = info.filename
            if not name:
                continue
            # Normalize to forward slashes; reject absolute or traversal.
            norm = name.replace('\\', '/')
            if norm.startswith('/') or norm.startswith('\\'):
                raise ContributionError(f'zip entry uses absolute path: {name!r}')
            if any(part == '..' for part in norm.split('/')):
                raise ContributionError(f'zip entry escapes archive: {name!r}')
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ContributionError(f'zip entry is a symlink: {name!r}')

        os.makedirs(dest_dir, exist_ok=True)
        dest_real = os.path.realpath(dest_dir)
        for info in zf.infolist():
            name = info.filename.replace('\\', '/')
            target = os.path.realpath(os.path.join(dest_dir, name))
            # Second-line defence: realpath must stay inside dest_dir.
            if not (target == dest_real or target.startswith(dest_real + os.sep)):
                raise ContributionError(
                    f'zip entry resolves outside extract dir: {name!r}'
                )
            if name.endswith('/'):
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, 'wb') as dst:
                shutil.copyfileobj(src, dst)


def _find_skill_md(extract_root: str) -> str:
    """Return absolute path to the SKILL.md the submission ships.

    Allowed layouts:
        <root>/SKILL.md
        <root>/<single-dir>/SKILL.md
    """
    direct = os.path.join(extract_root, 'SKILL.md')
    if os.path.isfile(direct):
        return direct
    entries = [e for e in os.listdir(extract_root) if not e.startswith('.')]
    if len(entries) == 1:
        nested = os.path.join(extract_root, entries[0], 'SKILL.md')
        if os.path.isfile(nested):
            return nested
    raise ContributionError(
        "missing SKILL.md — put it at the ZIP root or inside one top-level folder"
    )


@dataclass
class _ValidatedMeta:
    name: str
    description: str
    license: str
    skill_root: str  # directory holding SKILL.md


def _validate_extracted(extract_root: str) -> _ValidatedMeta:
    skill_md = _find_skill_md(extract_root)
    try:
        post = frontmatter.load(skill_md)
    except Exception as exc:
        raise ContributionError(f'cannot read SKILL.md: {exc}')
    name = (post.get('name') or '').strip()
    description = (post.get('description') or '').strip()
    license_ = (post.get('license') or '').strip()
    if not name:
        raise ContributionError('SKILL.md frontmatter is missing required `name`')
    if not _NAME_RE.match(name):
        raise ContributionError(
            "SKILL.md `name` must be ASCII letters, digits, dots, dashes or "
            "underscores (max 128 chars)"
        )
    if not description:
        raise ContributionError('SKILL.md frontmatter is missing required `description`')
    if len(description) > 4000:
        description = description[:4000]
    return _ValidatedMeta(
        name=name,
        description=description,
        license=license_[:200],
        skill_root=os.path.dirname(skill_md),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_submission(
    *,
    submitter: str | None,
    submitter_ip: str | None,
    zip_bytes: bytes,
    original_filename: str | None,
    max_uncompressed_bytes: int = 25 * 1024 * 1024,
) -> dict:
    """Persist a new submission, returning the stored row as a dict.

    Raises ContributionError for any user-facing validation failure.
    """
    _require_ready()
    if not zip_bytes:
        raise ContributionError('empty upload')

    now = time.time()
    # Reserve the row first so we have an integer id to key the blob dir on.
    with _lock:
        assert _conn is not None
        cur = _conn.execute(
            'INSERT INTO submissions '
            '(slug, title, description, license, submitter, submitter_ip, status, '
            ' file_path, file_size, original_filename, created_ts, updated_ts) '
            "VALUES (?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?, ?)",
            (
                '__pending__', '__pending__', '', '',
                submitter, submitter_ip,
                '', len(zip_bytes), (original_filename or '')[:200],
                now, now,
            ),
        )
        sub_id = cur.lastrowid

    blob_root = os.path.join(_blob_dir, str(sub_id))   # type: ignore[arg-type]
    extract_root = os.path.join(blob_root, 'extracted')
    zip_path = os.path.join(blob_root, 'skill.zip')

    try:
        os.makedirs(blob_root, exist_ok=True)
        # Persist the original archive verbatim for download/audit.
        with open(zip_path, 'wb') as f:
            f.write(zip_bytes)
        _safe_extract(zip_bytes, extract_root, max_uncompressed_bytes)
        meta = _validate_extracted(extract_root)
        slug_base = _slugify(meta.name)
        with _lock:
            slug = _unique_slug(slug_base)
            _conn.execute(  # type: ignore[union-attr]
                'UPDATE submissions SET slug=?, title=?, description=?, license=?, '
                'file_path=?, updated_ts=? WHERE id=?',
                (slug, meta.name, meta.description, meta.license, zip_path, now, sub_id),
            )
        _system_comment(sub_id, ROLE_SYSTEM, 'submitted')
    except Exception as exc:
        # Roll back: remove blob dir + row so the user can retry cleanly.
        shutil.rmtree(blob_root, ignore_errors=True)
        with _lock:
            _conn.execute('DELETE FROM submissions WHERE id=?', (sub_id,))   # type: ignore[union-attr]
        if isinstance(exc, ContributionError):
            raise
        raise ContributionError(f'submission rejected: {exc}')

    row = get_submission(sub_id, include_comments=False)
    assert row is not None
    return row


def _system_comment(submission_id: int, role: str, body: str) -> None:
    """Insert a system-audit comment without surfacing it as a user note."""
    add_comment(submission_id, author=None, author_role=role, body=body)


def add_comment(
    submission_id: int,
    *,
    author: str | None,
    author_role: str,
    body: str,
) -> dict:
    _require_ready()
    body = (body or '').strip()
    if not body:
        raise ContributionError('comment body required')
    if len(body) > 4000:
        body = body[:4000]
    if author_role not in ALL_ROLES:
        raise ContributionError(f'unknown author_role {author_role!r}')
    now = time.time()
    with _lock:
        cur = _conn.execute(  # type: ignore[union-attr]
            'INSERT INTO submission_comments (submission_id, author, author_role, body, created_ts) '
            'VALUES (?, ?, ?, ?, ?)',
            (submission_id, author, author_role, body, now),
        )
        _conn.execute(  # type: ignore[union-attr]
            'UPDATE submissions SET updated_ts=? WHERE id=?', (now, submission_id),
        )
        comment_id = cur.lastrowid
    return {
        'id': comment_id,
        'submissionId': submission_id,
        'author': author,
        'authorRole': author_role,
        'body': body,
        'createdTs': now,
    }


def update_status(
    submission_id: int,
    *,
    new_status: str,
    actor: str | None,
    actor_role: str,
    comment_body: str | None = None,
) -> dict:
    """Transition the submission's status and append a system audit line.

    Caller passes a free-form `comment_body` to attach reviewer rationale
    in the same operation.
    """
    _require_ready()
    if new_status not in ALL_STATUSES:
        raise ContributionError(f'unknown status {new_status!r}')

    sub = get_submission(submission_id, include_comments=False)
    if sub is None:
        raise ContributionError('submission not found', http_status=404)
    current = sub['status']
    if current == new_status:
        # Idempotent no-op; still accept an attached comment.
        if comment_body:
            add_comment(submission_id, author=actor, author_role=actor_role, body=comment_body)
        return get_submission(submission_id, include_comments=False)  # type: ignore[return-value]
    if new_status not in _LEGAL_TRANSITIONS.get(current, set()):
        raise ContributionError(
            f"cannot move submission from {current!r} to {new_status!r}",
        )

    now = time.time()
    with _lock:
        _conn.execute(  # type: ignore[union-attr]
            'UPDATE submissions SET status=?, updated_ts=? WHERE id=?',
            (new_status, now, submission_id),
        )
    audit = f'status: {current} → {new_status}'
    if actor:
        audit = f'{audit} (by {actor})'
    _system_comment(submission_id, ROLE_SYSTEM, audit)
    if comment_body:
        add_comment(submission_id, author=actor, author_role=actor_role, body=comment_body)
    return get_submission(submission_id, include_comments=False)  # type: ignore[return-value]


def publish_submission(
    submission_id: int,
    *,
    actor: str | None,
    skill_repo_path: str,
) -> dict:
    """Copy the extracted skill into SKILL_REPO_PATH and mark published.

    The destination directory name is the submission slug; if that name
    already exists in the live repo, a numeric suffix is appended so we
    never overwrite an existing entry.
    """
    _require_ready()
    sub = get_submission(submission_id, include_comments=False)
    if sub is None:
        raise ContributionError('submission not found', http_status=404)
    if sub['status'] != STATUS_APPROVED:
        raise ContributionError(
            f"can only publish approved submissions (current: {sub['status']})",
        )

    blob_root = os.path.join(_blob_dir, str(submission_id))  # type: ignore[arg-type]
    extract_root = os.path.join(blob_root, 'extracted')
    meta = _validate_extracted(extract_root)
    src = meta.skill_root

    os.makedirs(skill_repo_path, exist_ok=True)
    target_name = sub['slug']
    target_dir = os.path.join(skill_repo_path, target_name)
    suffix = 1
    while os.path.exists(target_dir):
        suffix += 1
        target_name = f"{sub['slug']}-{suffix}"
        target_dir = os.path.join(skill_repo_path, target_name)

    shutil.copytree(src, target_dir)

    now = time.time()
    with _lock:
        _conn.execute(  # type: ignore[union-attr]
            'UPDATE submissions SET status=?, updated_ts=?, published_skill_dir=? WHERE id=?',
            (STATUS_PUBLISHED, now, target_dir, submission_id),
        )
    audit = f'published into {target_name}'
    if actor:
        audit = f'{audit} (by {actor})'
    _system_comment(submission_id, ROLE_SYSTEM, audit)
    return get_submission(submission_id, include_comments=False)  # type: ignore[return-value]


def delete_submission(submission_id: int, *, actor: str | None) -> None:
    """Purge the submission's row, comments, and blob directory."""
    _require_ready()
    sub = get_submission(submission_id, include_comments=False)
    if sub is None:
        return
    if sub['status'] == STATUS_PUBLISHED:
        raise ContributionError(
            'published submissions cannot be deleted; revert in skill_repo manually',
        )
    blob_root = os.path.join(_blob_dir, str(submission_id))  # type: ignore[arg-type]
    shutil.rmtree(blob_root, ignore_errors=True)
    with _lock:
        _conn.execute(  # type: ignore[union-attr]
            'DELETE FROM submission_comments WHERE submission_id=?', (submission_id,),
        )
        _conn.execute(  # type: ignore[union-attr]
            'DELETE FROM submissions WHERE id=?', (submission_id,),
        )
    logger.info('submission %d deleted by %s', submission_id, actor or '?')


def get_submission(submission_id: int, *, include_comments: bool = True) -> dict | None:
    _require_ready()
    with _lock:
        row = _conn.execute(  # type: ignore[union-attr]
            'SELECT id, slug, title, description, license, submitter, submitter_ip, '
            'status, file_path, file_size, original_filename, created_ts, updated_ts, '
            'published_skill_dir, last_ai_review_ts '
            'FROM submissions WHERE id=?',
            (submission_id,),
        ).fetchone()
    if row is None:
        return None
    data = _row_to_dict(row)
    if include_comments:
        data['comments'] = _list_comments(submission_id)
    return data


def list_submissions(
    *,
    status_filter: str | None = None,
    submitter_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    _require_ready()
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    where = []
    params: list = []
    if status_filter:
        if status_filter not in ALL_STATUSES:
            raise ContributionError(f'unknown status filter {status_filter!r}')
        where.append('status = ?')
        params.append(status_filter)
    if submitter_filter:
        where.append('submitter = ?')
        params.append(submitter_filter)
    clause = (' WHERE ' + ' AND '.join(where)) if where else ''
    sql = (
        'SELECT id, slug, title, description, license, submitter, submitter_ip, '
        'status, file_path, file_size, original_filename, created_ts, updated_ts, '
        'published_skill_dir, last_ai_review_ts FROM submissions' + clause +
        ' ORDER BY updated_ts DESC LIMIT ? OFFSET ?'
    )
    count_sql = 'SELECT COUNT(*) FROM submissions' + clause

    with _lock:
        rows = _conn.execute(sql, (*params, limit, offset)).fetchall()  # type: ignore[union-attr]
        total = _conn.execute(count_sql, tuple(params)).fetchone()[0]  # type: ignore[union-attr]
    return {
        'rows': [_row_to_dict(r) for r in rows],
        'total': total,
    }


def list_extracted_files(submission_id: int) -> list[dict]:
    """Return a flat listing of files in the extracted bundle.

    Used by the review UI. Each entry is `{name, relPath, size}` with
    `relPath` relative to the extracted root.
    """
    _require_ready()
    blob_root = os.path.join(_blob_dir, str(submission_id))  # type: ignore[arg-type]
    extract_root = os.path.join(blob_root, 'extracted')
    if not os.path.isdir(extract_root):
        return []
    items: list[dict] = []
    for dirpath, _dirs, files in os.walk(extract_root):
        for fname in files:
            full = os.path.join(dirpath, fname)
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            items.append({
                'name': fname,
                'relPath': os.path.relpath(full, extract_root).replace('\\', '/'),
                'size': size,
            })
    items.sort(key=lambda i: (0 if i['name'] == 'SKILL.md' else 1, i['relPath']))
    return items


def _row_to_dict(r) -> dict:
    return {
        'id': r[0],
        'slug': r[1],
        'title': r[2],
        'description': r[3],
        'license': r[4],
        'submitter': r[5],
        'submitterIp': r[6],
        'status': r[7],
        'filePath': r[8],
        'fileSize': r[9],
        'originalFilename': r[10],
        'createdTs': r[11],
        'updatedTs': r[12],
        'publishedSkillDir': r[13],
        'last_ai_review_ts': r[14] if len(r) > 14 else None,
    }


def _list_comments(submission_id: int) -> list[dict]:
    with _lock:
        rows = _conn.execute(  # type: ignore[union-attr]
            'SELECT id, author, author_role, body, created_ts '
            'FROM submission_comments WHERE submission_id=? ORDER BY created_ts ASC, id ASC',
            (submission_id,),
        ).fetchall()
    return [
        {
            'id': r[0],
            'author': r[1],
            'authorRole': r[2],
            'body': r[3],
            'createdTs': r[4],
        }
        for r in rows
    ]


def _reset_for_tests() -> None:
    """Tear down module state. Tests only."""
    global _conn, _initialized, _disabled, _db_path, _blob_dir
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
        _conn = None
        _initialized = False
        _disabled = False
        _db_path = None
        _blob_dir = None
