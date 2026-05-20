"""Unit tests for the usage event store."""
import time

import pytest

from skills import usage


@pytest.fixture
def fresh_usage(tmp_path):
    """Open a fresh on-disk usage DB per test."""
    usage._reset_for_tests()
    db_path = tmp_path / 'usage.sqlite3'
    ok = usage.init_usage(str(db_path), retention_days=90)
    assert ok, 'init_usage should succeed on a writable tmp path'
    yield db_path
    usage._reset_for_tests()


def test_record_and_query_summary(fresh_usage):
    usage.record_event('install', skill='pdf-fill', target='claudeCode',
                       user='alice', status=200, latency_ms=42)
    usage.record_event('install', skill='pdf-fill', target='claudeCode',
                       user='alice', status=500, latency_ms=12)
    usage.record_event('pageview', skill='pdf-fill', user='alice',
                       status=200, latency_ms=5)
    usage.record_event('api', skill='pdf-fill', status=404, latency_ms=1)

    summary = usage.query_summary(range_seconds=3600)
    assert summary['installs'] == 2
    assert summary['pageviews'] == 1
    assert summary['apiCalls'] == 1
    assert summary['apiErrors'] == 1
    assert summary['errorRate'] == 1.0
    assert summary['uniqueSkills'] == 1


def test_query_installs_by_skill_and_target(fresh_usage):
    for _ in range(3):
        usage.record_event('install', skill='a', target='claudeCode',
                           user='u', status=200)
    usage.record_event('install', skill='a', target='opencode',
                       user='u', status=200)
    usage.record_event('install', skill='b', target='claudeCode',
                       user='u', status=200)
    # Error rows should not be counted.
    usage.record_event('install', skill='b', target='claudeCode',
                       user='u', status=500)

    by_skill = usage.query_installs(range_seconds=3600, group_by='skill')
    assert by_skill['groupBy'] == 'skill'
    rows = {r['skill']: r for r in by_skill['rows']}
    assert rows['a']['count'] == 4
    assert rows['a']['primaryTarget'] == 'claudeCode'
    assert rows['b']['count'] == 1

    by_target = usage.query_installs(range_seconds=3600, group_by='target')
    counts = {r['target']: r['count'] for r in by_target['rows']}
    assert counts == {'claudeCode': 4, 'opencode': 1}


def test_query_health_reports_last_parse_and_errors(fresh_usage):
    usage.record_event('parse', latency_ms=120, extra={'skillCount': 7})
    usage.record_event('parse_error', extra={'error': 'bad frontmatter'})
    usage.record_event('api', status=500, latency_ms=2)

    health = usage.query_health(range_seconds=3600)
    assert health['lastParse']['latencyMs'] == 120
    assert health['lastParse']['skillCount'] == 7
    assert health['parseErrors'] == 1
    assert health['statusBuckets']['5xx'] == 1


def test_prune_drops_old_rows(fresh_usage):
    usage.record_event('install', skill='old', target='claudeCode',
                       user='u', status=200)
    # Backdate the single row past the retention cutoff.
    with usage._lock:
        usage._conn.execute(
            'UPDATE events SET ts = ? WHERE skill = ?',
            (time.time() - 100 * 86400, 'old'),
        )
    usage.record_event('install', skill='new', target='claudeCode',
                       user='u', status=200)

    deleted = usage.prune(retention_days=90)
    assert deleted == 1

    rows = usage.query_installs(range_seconds=200 * 86400)['rows']
    assert [r['skill'] for r in rows] == ['new']


def test_record_event_swallows_when_disabled():
    """A broken DB must not raise into the calling request."""
    usage._reset_for_tests()
    # Skip init entirely → module is in the uninitialised / disabled state.
    usage.record_event('install', skill='x', target='t', user='u', status=200)
    # Must not raise.


def test_extra_payload_is_clamped(fresh_usage):
    long_msg = 'x' * 2000
    usage.record_event('parse_error', extra={'error': long_msg})

    health = usage.query_health(range_seconds=3600)
    assert health['parseErrors'] == 1
    parse_errors = [e for e in health['recentErrors'] if e['type'] == 'parse_error']
    assert parse_errors, 'recentErrors should include the parse_error row'
    assert len(parse_errors[0]['extra']) <= 500
