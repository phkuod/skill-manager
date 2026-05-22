"""Tests for UsageRecordingMiddleware."""
import pytest
from django.test import Client

from skills import usage


@pytest.fixture(autouse=True)
def _usage_db(tmp_path, settings):
    settings.USAGE_DB_PATH = str(tmp_path / 'usage.sqlite3')
    usage._reset_for_tests()
    usage.init_usage(settings.USAGE_DB_PATH, retention_days=90)
    yield
    usage._reset_for_tests()


@pytest.mark.django_db
def test_home_pageview_is_recorded():
    Client().get('/')
    summary = usage.query_summary(range_seconds=3600)
    assert summary['pageviews'] >= 1


@pytest.mark.django_db
def test_api_call_is_recorded():
    Client().get('/api/health')
    summary = usage.query_summary(range_seconds=3600)
    assert summary['apiCalls'] >= 1


@pytest.mark.django_db
def test_4xx_api_increments_error_count():
    Client().get('/api/skills/this-skill-does-not-exist')
    summary = usage.query_summary(range_seconds=3600)
    assert summary['apiErrors'] >= 1


@pytest.mark.django_db
def test_static_paths_are_skipped():
    Client().get('/static/skills/css/app.css')
    summary = usage.query_summary(range_seconds=3600)
    assert summary['pageviews'] == 0
    assert summary['apiCalls'] == 0


@pytest.mark.django_db
def test_middleware_swallows_record_failures(monkeypatch):
    """A broken record_event must NOT 500 the underlying request."""
    def boom(*a, **kw):
        raise RuntimeError('simulated failure')

    monkeypatch.setattr(usage, 'record_event', boom)
    resp = Client().get('/')
    assert resp.status_code == 200
