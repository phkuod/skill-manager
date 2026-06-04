"""Tests for the /usage HTML page and /api/usage/* JSON endpoints."""
import pytest
from django.test import Client

from skills import usage


@pytest.fixture(autouse=True)
def _usage_db(tmp_path, settings):
    settings.USAGE_ADMIN_USERS = {'alice'}
    settings.USAGE_DB_PATH = str(tmp_path / 'usage.sqlite3')
    usage._reset_for_tests()
    usage.init_usage(settings.USAGE_DB_PATH, retention_days=90)
    usage.record_event('install', skill='pdf-fill', target='claudeCode',
                       user='alice', status=200, latency_ms=10)
    usage.record_event('pageview', skill='pdf-fill', user='alice',
                       status=200, latency_ms=4)
    yield
    usage._reset_for_tests()


def _admin_client():
    c = Client()
    c.cookies['CURRENT_USER_NAME'] = 'alice'
    return c


@pytest.mark.django_db
def test_usage_page_forbidden_without_cookie():
    resp = Client().get('/usage/')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_usage_page_forbidden_for_non_admin():
    c = Client()
    c.cookies['CURRENT_USER_NAME'] = 'mallory'
    resp = c.get('/usage/')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_usage_page_renders_for_admin():
    resp = _admin_client().get('/usage/')
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'Usage dashboard' in body
    assert 'pdf-fill' in body


@pytest.mark.django_db
def test_api_usage_summary_returns_counts():
    resp = _admin_client().get('/api/usage/summary?range=24h')
    assert resp.status_code == 200
    data = resp.json()
    assert data['installs'] == 1
    assert data['pageviews'] == 1
    assert data['range'] == '24h'


@pytest.mark.django_db
def test_api_usage_summary_rejects_garbage_range():
    resp = _admin_client().get('/api/usage/summary?range=notarange')
    assert resp.status_code == 200
    assert resp.json()['range'] == '7d'


@pytest.mark.django_db
def test_api_usage_installs_groupby_target():
    resp = _admin_client().get('/api/usage/installs?range=7d&group=target')
    assert resp.status_code == 200
    data = resp.json()
    assert data['groupBy'] == 'target'
    assert data['rows'][0]['target'] == 'claudeCode'


@pytest.mark.django_db
def test_api_usage_endpoints_require_admin():
    paths = [
        '/api/usage/summary',
        '/api/usage/installs',
        '/api/usage/pageviews',
        '/api/usage/health',
    ]
    c = Client()
    for p in paths:
        assert c.get(p).status_code == 403


@pytest.mark.django_db
def test_empty_allowlist_forbids_everyone(settings):
    settings.USAGE_ADMIN_USERS = set()
    resp = _admin_client().get('/usage/')
    assert resp.status_code == 403
