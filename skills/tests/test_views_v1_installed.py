import pytest
from django.test import Client, override_settings


@pytest.fixture
def client():
    return Client()


def test_v1_installed_list_missing_cookie_envelope(client):
    with override_settings(INSTALL_TARGETS={'F12': {'type': 'local', 'base': '/tmp/{user_name}/skills'}}):
        res = client.get('/api/v1/install/targets/F12/skills')
    assert res.status_code == 400
    err = res.json()['error']
    assert 'code' in err and 'message' in err


def test_v1_installed_list_happy_path(client, tmp_path):
    (tmp_path / 'coman' / 'skills' / 'coding-guide').mkdir(parents=True)
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={'F12': cfg}):
        res = client.get('/api/v1/install/targets/F12/skills')
    assert res.status_code == 200
    body = res.json()
    assert 'data' in body
    assert body['data']['target'] == 'F12'


def test_v1_installed_uninstall_unknown_target_envelope(client):
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={}):
        res = client.post('/api/v1/install/targets/NOPE/skills/coding-guide/uninstall')
    assert res.status_code == 400
    body = res.json()
    assert body['error']['code'] == 'INSTALL_TARGET_INVALID'


def test_v1_installed_uninstall_happy_path(client, tmp_path):
    (tmp_path / 'coman' / 'skills' / 'coding-guide').mkdir(parents=True)
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={'F12': cfg}):
        res = client.post('/api/v1/install/targets/F12/skills/coding-guide/uninstall')
    assert res.status_code == 200
    body = res.json()
    assert body['data']['status'] == 'ok'
    assert body['data']['target'] == 'F12'
