"""Regression: contributions DB upgrade path from a pre-M1 schema.

The M1 ``last_ai_review_ts`` column + its index must be applied to an
*existing* submissions table without crashing init. The rest of the
suite always starts from a fresh ``init_submissions`` (column present via
CREATE TABLE), so it never exercised the upgrade path — where the table
already exists and the column is absent. Creating the index inside the
schema script (before the additive ALTER) crashed init on such a DB.
"""
from __future__ import annotations

import sqlite3

from skills import contributions


# Pre-M1 submissions schema: note there is NO last_ai_review_ts column and
# NO idx_subs_last_ai_review index.
_OLD_SCHEMA = """
CREATE TABLE submissions (
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
  published_skill_dir   TEXT
);
CREATE INDEX idx_subs_status_updated ON submissions(status, updated_ts DESC);
CREATE INDEX idx_subs_submitter ON submissions(submitter);
CREATE TABLE submission_comments (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  author        TEXT,
  author_role   TEXT NOT NULL,
  body          TEXT NOT NULL,
  created_ts    REAL NOT NULL
);
"""


def _write_old_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(_OLD_SCHEMA)
    conn.commit()
    conn.close()


def _columns(path, table):
    conn = sqlite3.connect(path)
    try:
        return {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}
    finally:
        conn.close()


def _indexes(path, table):
    conn = sqlite3.connect(path)
    try:
        return {row[1] for row in conn.execute(f'PRAGMA index_list({table})')}
    finally:
        conn.close()


def test_init_upgrades_pre_m1_db_without_crashing(tmp_path):
    db = tmp_path / 'old.sqlite3'
    _write_old_db(str(db))
    assert 'last_ai_review_ts' not in _columns(str(db), 'submissions')

    contributions._reset_for_tests()
    try:
        ok = contributions.init_submissions(str(db), str(tmp_path / 'blobs'))
        assert ok is True
    finally:
        contributions._reset_for_tests()

    # Column + index were added by the migration helper.
    assert 'last_ai_review_ts' in _columns(str(db), 'submissions')
    assert 'idx_subs_last_ai_review' in _indexes(str(db), 'submissions')


def test_init_is_idempotent_on_already_upgraded_db(tmp_path):
    db = tmp_path / 'fresh.sqlite3'

    # First init builds the current schema from scratch.
    contributions._reset_for_tests()
    assert contributions.init_submissions(str(db), str(tmp_path / 'blobs')) is True
    contributions._reset_for_tests()

    # Second init over the same file must not raise (duplicate column /
    # existing index both tolerated).
    assert contributions.init_submissions(str(db), str(tmp_path / 'blobs')) is True
    contributions._reset_for_tests()

    assert 'idx_subs_last_ai_review' in _indexes(str(db), 'submissions')
