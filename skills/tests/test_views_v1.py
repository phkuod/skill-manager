"""Tests for the /api/v1/* surface — envelope shape and error codes."""
import json
import os
import shutil

import pytest
from django.test import Client

from skills import envelope as e


SKILL_REPO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'skill_repo')
)
VERSION_FIXTURE = os.path.join(SKILL_REPO_PATH, 'webapp-testing', '20260331-version-test')


def _create_version_fixture():
    os.makedirs(VERSION_FIXTURE, exist_ok=True)
    with open(os.path.join(VERSION_FIXTURE, 'SKILL.md'), 'w') as f:
        f.write(
            '---\n'
            'name: webapp-testing\n'
            'description: "Versioned webapp testing skill"\n'
            'license: Complete terms in LICENSE.txt\n'
            '---\n\n'
            'Versioned content for webapp-testing.\n'
        )


def _remove_version_fixture():
    if os.path.exists(VERSION_FIXTURE):
        shutil.rmtree(VERSION_FIXTURE, ignore_errors=True)


@pytest.fixture(scope='module', autouse=True)
def version_fixture():
    _remove_version_fixture()
    _create_version_fixture()
    import skills.watcher as watcher
    from skills.parser import parse_all_skills
    watcher._skills = parse_all_skills(SKILL_REPO_PATH)
    yield
    _remove_version_fixture()


@pytest.fixture
def client():
    return Client()


# ---------------------------------------------------------------------------
# /api/version — discovery
# ---------------------------------------------------------------------------

def test_version_discovery(client):
    res = client.get('/api/version')
    assert res.status_code == 200
    data = res.json()
    assert data['app'] == 'skill-market'
    assert 'v1' in data['apiVersions']


# ---------------------------------------------------------------------------
# Envelope shape — success
# ---------------------------------------------------------------------------

def test_v1_health_envelope(client):
    res = client.get('/api/v1/health')
    assert res.status_code == 200
    body = res.json()
    assert 'data' in body
    assert body['data']['status'] == 'ok'
    assert isinstance(body['data']['skillCount'], int)


def test_v1_install_targets_envelope(client):
    res = client.get('/api/v1/install/targets')
    assert res.status_code == 200
    body = res.json()
    assert 'data' in body
    assert 'targets' in body['data']
    assert isinstance(body['data']['targets'], list)


def test_v1_skill_list_envelope_and_meta(client):
    res = client.get('/api/v1/skills')
    assert res.status_code == 200
    body = res.json()
    assert 'data' in body
    assert isinstance(body['data'], list)
    assert 'meta' in body
    for key in ('page', 'limit', 'total', 'hasNext'):
        assert key in body['meta']


def test_v1_skill_list_pagination(client):
    res = client.get('/api/v1/skills?limit=5&page=1')
    body = res.json()
    assert len(body['data']) == 5
    assert body['meta']['page'] == 1
    assert body['meta']['limit'] == 5
    assert body['meta']['hasNext'] is True


def test_v1_skill_list_link_header(client):
    res = client.get('/api/v1/skills?limit=5')
    assert 'Link' in res
    assert 'page=2' in res['Link']
    assert 'rel="next"' in res['Link']


def test_v1_skill_list_excludes_contentHtml(client):
    # Same projection as legacy /api/skills.
    res = client.get('/api/v1/skills')
    for skill in res.json()['data']:
        assert 'contentHtml' not in skill


def test_v1_skill_detail_envelope(client):
    res = client.get('/api/v1/skills/pdf')
    assert res.status_code == 200
    body = res.json()
    assert body['data']['name'] == 'pdf'
    assert 'installPaths' in body['data']
    assert 'repoPath' in body['data']


def test_v1_skill_files_envelope(client):
    res = client.get('/api/v1/skills/pdf/files')
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body['data'], list)
    paths = [f['path'] for f in body['data']]
    assert 'SKILL.md' in paths


def test_v1_versions_envelope(client):
    res = client.get('/api/v1/skills/webapp-testing/versions')
    assert res.status_code == 200
    body = res.json()
    assert body['data']['skill'] == 'webapp-testing'
    assert isinstance(body['data']['versions'], list)


def test_v1_version_detail_envelope(client):
    res = client.get('/api/v1/skills/webapp-testing/versions/20260331-version-test')
    assert res.status_code == 200
    body = res.json()
    assert body['data']['name'] == 'webapp-testing'
    assert 'Versioned content' in body['data']['content']


def test_v1_version_files_envelope(client):
    res = client.get('/api/v1/skills/webapp-testing/versions/20260331-version-test/files')
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body['data'], list)


# ---------------------------------------------------------------------------
# Error envelope — codes
# ---------------------------------------------------------------------------

def test_v1_skill_detail_404_uses_skill_not_found_code(client):
    res = client.get('/api/v1/skills/does-not-exist')
    assert res.status_code == 404
    body = res.json()
    assert body['error']['code'] == e.SKILL_NOT_FOUND
    assert 'does-not-exist' in body['error']['message']


def test_v1_skill_files_404_uses_skill_not_found_code(client):
    res = client.get('/api/v1/skills/does-not-exist/files')
    assert res.status_code == 404
    assert res.json()['error']['code'] == e.SKILL_NOT_FOUND


def test_v1_version_detail_404_uses_version_not_found_code(client):
    res = client.get('/api/v1/skills/webapp-testing/versions/99990101-fake')
    assert res.status_code == 404
    assert res.json()['error']['code'] == e.VERSION_NOT_FOUND


def test_v1_version_files_dotdot_still_rejected(client):
    # Path-traversal protection still applies via the shared _version_dir.
    res = client.get('/api/v1/skills/webapp-testing/versions/../files')
    assert res.status_code == 404
    assert res.json()['error']['code'] == e.VERSION_NOT_FOUND


# ---------------------------------------------------------------------------
# Install error envelope
# ---------------------------------------------------------------------------

def test_v1_install_missing_cookie(client):
    res = client.post('/api/v1/skills/pdf/install', data='{}',
                      content_type='application/json')
    assert res.status_code == 400
    assert res.json()['error']['code'] == e.INSTALL_USERNAME_INVALID


def test_v1_install_invalid_json_body(client):
    client.cookies['CURRENT_USER_NAME'] = 'jdoe'
    res = client.post('/api/v1/skills/pdf/install', data='not-json{',
                      content_type='application/json')
    assert res.status_code == 400
    assert res.json()['error']['code'] == e.INVALID_BODY


def test_v1_install_missing_target(client):
    client.cookies['CURRENT_USER_NAME'] = 'jdoe'
    res = client.post('/api/v1/skills/pdf/install',
                      data=json.dumps({}),
                      content_type='application/json')
    assert res.status_code == 400
    assert res.json()['error']['code'] == e.INVALID_BODY


def test_v1_install_unknown_target_maps_to_install_target_invalid(client, settings):
    # InstallError.code carries through to the envelope.
    settings.INSTALL_TARGETS = {}  # no targets configured
    client.cookies['CURRENT_USER_NAME'] = 'jdoe'
    res = client.post('/api/v1/skills/pdf/install',
                      data=json.dumps({'target': 'F99'}),
                      content_type='application/json')
    assert res.status_code == 400
    assert res.json()['error']['code'] == e.INSTALL_TARGET_INVALID


def test_v1_install_skill_not_found(client):
    client.cookies['CURRENT_USER_NAME'] = 'jdoe'
    res = client.post('/api/v1/skills/does-not-exist/install',
                      data=json.dumps({'target': 'LOCAL'}),
                      content_type='application/json')
    assert res.status_code == 404
    assert res.json()['error']['code'] == e.SKILL_NOT_FOUND
