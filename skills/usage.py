"""Usage event storage.

A small file-backed SQLite event log so operators can answer "what is
happening on this server?" without grepping rotating logs. The DB lives
outside the Django ORM on purpose — the project intentionally keeps
`INSTALLED_APPS` minimal and uses `:memory:` for the default database.

Public surface:
    init_usage(db_path, retention_days)  — open conn + start prune thread.
    record_event(...)                    — single INSERT, swallows errors.
    query_summary / query_installs /
    query_pageviews / query_health       — read-side helpers for views.
    prune(retention_days)                — DELETE old rows.

`record_event` MUST NOT raise. A broken usage DB must never take down a
real request.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time

logger = logging.getLogger('skills.usage')

_PRUNE_INTERVAL_SECONDS = 24 * 60 * 60
_EXTRA_MAX_CHARS = 500

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()
_initialized = False
_disabled = False
_db_path: str | None = None
_retention_days = 90


_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ts         REAL    NOT NULL,
  type       TEXT    NOT NULL,
  skill      TEXT,
  version    TEXT,
  target     TEXT,
  user       TEXT,
  status     INTEGER,
  latency_ms INTEGER,
  extra      TEXT,
  ip         TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts        ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_type_ts   ON events(type, ts);
CREATE INDEX IF NOT EXISTS idx_events_skill_ts  ON events(skill, ts);
"""


def _ensure_ip_column(conn: sqlite3.Connection) -> None:
    """Add the ip column to pre-existing event tables.

    SQLite has no IF NOT EXISTS on ALTER TABLE; we treat 'duplicate column'
    as success so upgrades stay idempotent.
    """
    try:
        conn.execute('ALTER TABLE events ADD COLUMN ip TEXT')
    except sqlite3.OperationalError as exc:
        if 'duplicate column' not in str(exc).lower():
            raise


def init_usage(db_path: str, retention_days: int = 90) -> bool:
    """Open the usage DB and start the background prune thread.

    Idempotent: subsequent calls are no-ops once initialised.
    Returns True on success, False if storage could not be opened (the
    module then disables itself and record_event becomes a no-op).
    """
    global _conn, _initialized, _disabled, _db_path, _retention_days

    with _lock:
        if _initialized:
            return not _disabled
        _initialized = True
        _db_path = db_path
        _retention_days = retention_days

        try:
            parent = os.path.dirname(db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            _conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
            _conn.execute('PRAGMA journal_mode=WAL')
            _conn.execute('PRAGMA synchronous=NORMAL')
            _conn.execute('PRAGMA busy_timeout=2000')
            _conn.executescript(_SCHEMA)
            _ensure_ip_column(_conn)
            _conn.execute('CREATE INDEX IF NOT EXISTS idx_events_ip_ts ON events(ip, ts)')
        except Exception as exc:
            _disabled = True
            _conn = None
            logger.error('usage DB init failed (%s): %s — usage tracking disabled', db_path, exc)
            return False

    try:
        prune(retention_days)
    except Exception as exc:
        logger.warning('initial usage prune failed: %s', exc)

    t = threading.Thread(target=_prune_loop, name='usage-prune', daemon=True)
    t.start()

    logger.info('usage DB ready (%s, retention=%d days)', db_path, retention_days)
    return True


def _prune_loop() -> None:
    while True:
        time.sleep(_PRUNE_INTERVAL_SECONDS)
        try:
            prune(_retention_days)
        except Exception as exc:
            logger.warning('periodic usage prune failed: %s', exc)


def record_event(
    type: str,
    *,
    skill: str | None = None,
    version: str | None = None,
    target: str | None = None,
    user: str | None = None,
    status: int | None = None,
    latency_ms: int | None = None,
    extra: dict | None = None,
    ip: str | None = None,
) -> None:
    """Insert one event row. Never raises."""
    if _disabled or _conn is None:
        return
    try:
        extra_json = None
        if extra is not None:
            payload = json.dumps(extra, default=str, ensure_ascii=False)
            if len(payload) > _EXTRA_MAX_CHARS:
                payload = payload[:_EXTRA_MAX_CHARS]
            extra_json = payload
        with _lock:
            _conn.execute(
                'INSERT INTO events (ts, type, skill, version, target, user, status, latency_ms, extra, ip) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (time.time(), type, skill, version, target, user, status, latency_ms, extra_json, ip),
            )
    except Exception as exc:
        logger.warning('record_event(%s) failed: %s', type, exc)


def prune(retention_days: int) -> int:
    """Delete rows older than retention_days. Returns rowcount."""
    if _disabled or _conn is None:
        return 0
    cutoff = time.time() - retention_days * 86400
    with _lock:
        cur = _conn.execute('DELETE FROM events WHERE ts < ?', (cutoff,))
        deleted = cur.rowcount or 0
    if deleted:
        logger.info('usage prune: deleted %d rows older than %d days', deleted, retention_days)
    return deleted


def _since(range_seconds: int) -> float:
    return time.time() - max(int(range_seconds), 1)


def _fetchall(sql: str, params: tuple = ()) -> list[tuple]:
    if _disabled or _conn is None:
        return []
    with _lock:
        return list(_conn.execute(sql, params).fetchall())


def query_summary(range_seconds: int) -> dict:
    since = _since(range_seconds)
    rows = _fetchall(
        'SELECT type, COUNT(*) FROM events WHERE ts >= ? GROUP BY type',
        (since,),
    )
    counts = {t: n for t, n in rows}
    total_api = counts.get('api', 0)
    error_rows = _fetchall(
        "SELECT COUNT(*) FROM events WHERE ts >= ? AND type='api' AND status >= 400",
        (since,),
    )
    errors = error_rows[0][0] if error_rows else 0
    unique_skills_rows = _fetchall(
        "SELECT COUNT(DISTINCT skill) FROM events "
        "WHERE ts >= ? AND skill IS NOT NULL AND type IN ('pageview','api')",
        (since,),
    )
    unique_skills = unique_skills_rows[0][0] if unique_skills_rows else 0
    return {
        'rangeSeconds': range_seconds,
        'installs': counts.get('install', 0),
        'uninstalls': counts.get('uninstall', 0),
        'pageviews': counts.get('pageview', 0),
        'apiCalls': total_api,
        'apiErrors': errors,
        'errorRate': round(errors / total_api, 4) if total_api else 0.0,
        'uniqueSkills': unique_skills,
        'parseEvents': counts.get('parse', 0),
        'parseErrors': counts.get('parse_error', 0),
    }


def query_installs(range_seconds: int, group_by: str = 'skill') -> dict:
    since = _since(range_seconds)
    if group_by == 'target':
        rows = _fetchall(
            "SELECT target, COUNT(*) c, MAX(ts) last FROM events "
            "WHERE ts >= ? AND type='install' AND status=200 "
            "GROUP BY target ORDER BY c DESC LIMIT 50",
            (since,),
        )
        return {
            'groupBy': 'target',
            'rows': [{'target': r[0] or '', 'count': r[1], 'lastTs': r[2]} for r in rows],
        }
    if group_by == 'day':
        rows = _fetchall(
            "SELECT CAST(ts/86400 AS INTEGER) day, COUNT(*) c FROM events "
            "WHERE ts >= ? AND type='install' AND status=200 "
            "GROUP BY day ORDER BY day ASC",
            (since,),
        )
        return {
            'groupBy': 'day',
            'rows': [{'day': r[0] * 86400, 'count': r[1]} for r in rows],
        }
    rows = _fetchall(
        "SELECT skill, COUNT(*) c, MAX(ts) last, "
        "  (SELECT target FROM events e2 "
        "   WHERE e2.skill = events.skill AND e2.type='install' AND e2.status=200 "
        "   GROUP BY target ORDER BY COUNT(*) DESC LIMIT 1) primary_target "
        "FROM events "
        "WHERE ts >= ? AND type='install' AND status=200 AND skill IS NOT NULL "
        "GROUP BY skill ORDER BY c DESC LIMIT 50",
        (since,),
    )
    return {
        'groupBy': 'skill',
        'rows': [
            {'skill': r[0], 'count': r[1], 'lastTs': r[2], 'primaryTarget': r[3] or ''}
            for r in rows
        ],
    }


def query_pageviews(range_seconds: int) -> dict:
    since = _since(range_seconds)
    rows = _fetchall(
        "SELECT skill, COUNT(*) c, MAX(ts) last FROM events "
        "WHERE ts >= ? AND type='pageview' AND skill IS NOT NULL "
        "GROUP BY skill ORDER BY c DESC LIMIT 50",
        (since,),
    )
    return {
        'rows': [{'skill': r[0], 'count': r[1], 'lastTs': r[2]} for r in rows],
    }


def query_health(range_seconds: int) -> dict:
    since = _since(range_seconds)
    parse_rows = _fetchall(
        "SELECT ts, latency_ms, extra FROM events "
        "WHERE type='parse' ORDER BY ts DESC LIMIT 1",
    )
    last_parse = None
    if parse_rows:
        ts, latency, extra = parse_rows[0]
        skill_count = None
        if extra:
            try:
                skill_count = json.loads(extra).get('skillCount')
            except ValueError:
                skill_count = None
        last_parse = {'ts': ts, 'latencyMs': latency, 'skillCount': skill_count}

    err_rows = _fetchall(
        "SELECT COUNT(*) FROM events WHERE ts >= ? AND type='parse_error'",
        (since,),
    )
    parse_errors = err_rows[0][0] if err_rows else 0

    status_rows = _fetchall(
        "SELECT CASE "
        "  WHEN status >= 500 THEN '5xx' "
        "  WHEN status >= 400 THEN '4xx' "
        "  WHEN status >= 300 THEN '3xx' "
        "  WHEN status >= 200 THEN '2xx' "
        "  ELSE 'other' END bucket, COUNT(*) "
        "FROM events WHERE ts >= ? AND type IN ('pageview','api') "
        "GROUP BY bucket",
        (since,),
    )
    buckets = {b: c for b, c in status_rows}

    recent_errors = _fetchall(
        "SELECT ts, type, skill, target, status, extra FROM events "
        "WHERE ts >= ? AND (type='parse_error' OR (status IS NOT NULL AND status >= 400)) "
        "ORDER BY ts DESC LIMIT 20",
        (since,),
    )

    return {
        'lastParse': last_parse,
        'parseErrors': parse_errors,
        'statusBuckets': {
            '2xx': buckets.get('2xx', 0),
            '3xx': buckets.get('3xx', 0),
            '4xx': buckets.get('4xx', 0),
            '5xx': buckets.get('5xx', 0),
        },
        'recentErrors': [
            {
                'ts': r[0],
                'type': r[1],
                'skill': r[2],
                'target': r[3],
                'status': r[4],
                'extra': r[5],
            }
            for r in recent_errors
        ],
    }


def query_timeseries(range_seconds: int) -> dict:
    """Bucketed event counts grouped by event type.

    Bucket width auto-picks 1 hour for ranges ≤ 24h, 1 day otherwise — so
    24h renders ~24 bars, 7d renders 7, 30d renders 30, 90d renders 90.

    Returns:
        {
            'bucketSeconds': int,
            'maxTotal': int,     # tallest stack across buckets, for y-scale
            'buckets': [{'ts': float, 'pageview': int, 'api': int,
                         'install': int, 'uninstall': int,
                         'parse_error': int, 'total': int}, ...]
        }
    """
    range_seconds = max(int(range_seconds), 1)
    bucket_seconds = 3600 if range_seconds <= 86400 else 86400
    since = time.time() - range_seconds

    rows = _fetchall(
        "SELECT CAST(ts/? AS INTEGER) bucket, type, COUNT(*) "
        "FROM events WHERE ts >= ? "
        "GROUP BY bucket, type ORDER BY bucket ASC",
        (bucket_seconds, since),
    )

    types_tracked = ('pageview', 'api', 'install', 'uninstall', 'parse_error')
    buckets_map: dict[int, dict] = {}
    for bucket, type_, count in rows:
        entry = buckets_map.setdefault(int(bucket), {t: 0 for t in types_tracked})
        if type_ in entry:
            entry[type_] = int(count)

    now_bucket = int(time.time()) // bucket_seconds
    start_bucket = int(since) // bucket_seconds + 1

    buckets: list[dict] = []
    max_total = 0
    for b in range(start_bucket, now_bucket + 1):
        counts = buckets_map.get(b, {t: 0 for t in types_tracked})
        total = sum(counts.values())
        buckets.append({
            'ts': float(b * bucket_seconds),
            **counts,
            'total': total,
        })
        if total > max_total:
            max_total = total

    return {
        'bucketSeconds': bucket_seconds,
        'maxTotal': max_total,
        'buckets': buckets,
    }


def query_recent(limit: int = 50, offset: int = 0) -> dict:
    """Return a window of recent events plus the total row count.

    Returns ``{'rows': [...], 'total': int}``. ``limit`` is clamped to
    [1, 200] and ``offset`` to >= 0.
    """
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    rows = _fetchall(
        "SELECT ts, type, skill, version, target, user, status, latency_ms, ip "
        "FROM events ORDER BY ts DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    total_rows = _fetchall("SELECT COUNT(*) FROM events")
    total = total_rows[0][0] if total_rows else 0
    return {
        'rows': [
            {
                'ts': r[0],
                'type': r[1],
                'skill': r[2],
                'version': r[3],
                'target': r[4],
                'user': r[5],
                'status': r[6],
                'latencyMs': r[7],
                'ip': r[8],
            }
            for r in rows
        ],
        'total': total,
    }


def _reset_for_tests() -> None:
    """Tear down module state. Used only by tests."""
    global _conn, _initialized, _disabled, _db_path
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
