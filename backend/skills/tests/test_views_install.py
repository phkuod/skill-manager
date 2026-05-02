import json

import pytest
from django.test import Client


@pytest.mark.django_db
def test_install_targets_returns_name_and_base_only(settings):
    settings.INSTALL_TARGETS = {
        'F12': {'type': 'local', 'base': '/AAA/{user_name}/skills'},
        'F15': {
            'type': 'ssh',
            'base': '/AAA/{user_name}/skills',
            'host': 'secret.host',
            'user': 'svc',
            'ssh_key': '/etc/ssh/secret',
        },
    }
    resp = Client().get('/api/install/targets')
    assert resp.status_code == 200
    data = resp.json()
    targets = sorted(data['targets'], key=lambda t: t['name'])
    assert targets == [
        {'name': 'F12', 'base': '/AAA/{user_name}/skills'},
        {'name': 'F15', 'base': '/AAA/{user_name}/skills'},
    ]
    body = resp.content.decode('utf-8')
    assert 'secret.host' not in body
    assert 'svc' not in body
    assert 'secret' not in body


def _client_with_cookie(name='jdoe'):
    c = Client()
    c.cookies['CURRENT_USER_NAME'] = name
    return c


@pytest.mark.django_db
def test_install_unknown_skill_returns_404(settings):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': '/tmp/x'}}
    c = _client_with_cookie()
    resp = c.post(
        '/api/skills/no-such-skill/install',
        data=json.dumps({'target': 'LOCAL'}),
        content_type='application/json',
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_install_missing_cookie_returns_400(settings, tmp_path):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': str(tmp_path)}}
    c = Client()
    from skills.watcher import get_skills
    skills = list(get_skills().keys())
    if not skills:
        pytest.skip('skill_repo empty')
    resp = c.post(
        f'/api/skills/{skills[0]}/install',
        data=json.dumps({'target': 'LOCAL'}),
        content_type='application/json',
    )
    assert resp.status_code == 400
    assert 'CURRENT_USER_NAME' in resp.json()['error']


@pytest.mark.django_db
def test_install_missing_target_returns_400(settings):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': '/tmp/x'}}
    c = _client_with_cookie()
    from skills.watcher import get_skills
    skills = list(get_skills().keys())
    if not skills:
        pytest.skip('skill_repo empty')
    resp = c.post(
        f'/api/skills/{skills[0]}/install',
        data=json.dumps({}),
        content_type='application/json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_install_unknown_target_returns_400(settings):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': '/tmp/x'}}
    c = _client_with_cookie()
    from skills.watcher import get_skills
    skills = list(get_skills().keys())
    if not skills:
        pytest.skip('skill_repo empty')
    resp = c.post(
        f'/api/skills/{skills[0]}/install',
        data=json.dumps({'target': 'F99'}),
        content_type='application/json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_install_invalid_json_returns_400(settings):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': '/tmp/x'}}
    c = _client_with_cookie()
    from skills.watcher import get_skills
    skills = list(get_skills().keys())
    if not skills:
        pytest.skip('skill_repo empty')
    resp = c.post(
        f'/api/skills/{skills[0]}/install',
        data='not-json',
        content_type='application/json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_install_success_copies_skill(settings, tmp_path):
    base = tmp_path / 'dst' / '{user_name}' / 'skills'
    settings.INSTALL_TARGETS = {
        'LOCAL': {'type': 'local', 'base': str(base)},
    }
    c = _client_with_cookie('jdoe')
    from skills.watcher import get_skills
    skills = list(get_skills().keys())
    if not skills:
        pytest.skip('skill_repo empty')
    skill_name = skills[0]

    resp = c.post(
        f'/api/skills/{skill_name}/install',
        data=json.dumps({'target': 'LOCAL'}),
        content_type='application/json',
    )

    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body['status'] == 'ok'
    assert body['target'] == 'LOCAL'
    expected_path = tmp_path / 'dst' / 'jdoe' / 'skills' / skill_name
    assert body['path'] == str(expected_path)
    assert expected_path.is_dir()
    assert (expected_path / 'SKILL.md').is_file()


@pytest.mark.django_db
def test_version_install_unknown_version_returns_404(settings, tmp_path):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': str(tmp_path)}}
    c = _client_with_cookie()
    from skills.watcher import get_skills
    skills = list(get_skills().keys())
    if not skills:
        pytest.skip('skill_repo empty')
    resp = c.post(
        f'/api/skills/{skills[0]}/versions/99999999-nope/install',
        data=json.dumps({'target': 'LOCAL'}),
        content_type='application/json',
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_version_install_unknown_skill_returns_404(settings, tmp_path):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': str(tmp_path)}}
    c = _client_with_cookie()
    resp = c.post(
        '/api/skills/no-such/versions/original/install',
        data=json.dumps({'target': 'LOCAL'}),
        content_type='application/json',
    )
    assert resp.status_code == 404
