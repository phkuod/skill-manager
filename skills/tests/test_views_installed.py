import os
from unittest.mock import patch

import pytest
from django.test import Client, override_settings


@pytest.fixture
def client():
    return Client()


# ---------- HTML page ----------

def test_installed_page_renders(client):
    cfg = {'type': 'local', 'base': '/tmp/{user_name}/skills'}
    with override_settings(INSTALL_TARGETS={'F12': cfg}):
        res = client.get('/installed/')
    assert res.status_code == 200
    body = res.content.decode('utf-8')
    assert 'Installed skills' in body
    # Bootstrap JSON block must be present and contain at least F12
    assert 'installed-bootstrap' in body
    assert 'F12' in body


# ---------- API list ----------

def test_api_installed_list_missing_cookie_returns_400(client):
    with override_settings(INSTALL_TARGETS={'F12': {'type': 'local', 'base': '/tmp/{user_name}/skills'}}):
        res = client.get('/api/install/targets/F12/skills')
    assert res.status_code == 400
    assert 'cookie' in res.json()['error'].lower()


def test_api_installed_list_unknown_target_returns_400(client):
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={}):
        res = client.get('/api/install/targets/NOPE/skills')
    assert res.status_code == 400
    assert 'unknown' in res.json()['error'].lower()


def test_api_installed_list_happy_path_local(client, tmp_path):
    (tmp_path / 'coman' / 'skills' / 'coding-guide').mkdir(parents=True)
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={'F12': cfg}):
        res = client.get('/api/install/targets/F12/skills')
    assert res.status_code == 200
    body = res.json()
    assert body['target'] == 'F12'
    assert body['base'].endswith(os.path.join('coman', 'skills'))
    names = {row['name'] for row in body['catalog']} | {row['name'] for row in body['orphan']}
    assert 'coding-guide' in names


# ---------- API uninstall ----------

def test_api_installed_uninstall_missing_cookie(client):
    with override_settings(INSTALL_TARGETS={'F12': {'type': 'local', 'base': '/tmp/{user_name}/skills'}}):
        res = client.post('/api/install/targets/F12/skills/coding-guide/uninstall')
    assert res.status_code == 400


def test_api_installed_uninstall_happy_path_local(client, tmp_path):
    (tmp_path / 'coman' / 'skills' / 'coding-guide').mkdir(parents=True)
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={'F12': cfg}):
        res = client.post('/api/install/targets/F12/skills/coding-guide/uninstall')
    assert res.status_code == 200
    body = res.json()
    assert body['status'] == 'ok'
    assert body['target'] == 'F12'
    assert not (tmp_path / 'coman' / 'skills' / 'coding-guide').exists()


def test_api_installed_uninstall_path_not_found(client, tmp_path):
    (tmp_path / 'coman' / 'skills').mkdir(parents=True)
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={'F12': cfg}):
        res = client.post('/api/install/targets/F12/skills/nope/uninstall')
    assert res.status_code == 404
