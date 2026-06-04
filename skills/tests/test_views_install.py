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


@pytest.mark.django_db
def test_version_install_uses_skill_name_not_version_for_destination(settings, tmp_path):
    """Versioned install must land at <base>/<skill_name>/, not <base>/<version>/.

    Regression for a bug where install_skill derived the destination dir name
    from os.path.basename(src_dir), which on a versioned install pointed at the
    dated subdir (e.g. '20260501-foo') instead of the canonical skill name.
    Downstream tools resolve skills by name (~/.claude/skills/<name>) so the
    dated dir name would have made the install effectively unfindable.
    """
    base = tmp_path / 'dst' / '{user_name}' / 'skills'
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': str(base)}}

    from skills.watcher import get_skills
    from django.conf import settings as dj_settings
    skills = get_skills()
    versioned = next(
        ((n, s) for n, s in skills.items() if s.get('versions')),
        None,
    )
    if versioned is None:
        # No naturally versioned skill in the repo — synthesize one in the
        # real skill_repo so the watcher and view layer pick it up.
        skill_name = next(iter(skills.keys()), None)
        if skill_name is None:
            pytest.skip('skill_repo empty')
        ver_path = (
            __import__('pathlib').Path(dj_settings.SKILL_REPO_PATH)
            / skill_name / '20260501-regression-test'
        )
        ver_path.mkdir(parents=True, exist_ok=True)
        (ver_path / 'SKILL.md').write_text(
            '---\nname: ' + skill_name + '\nlicense: MIT\n---\nv', encoding='utf-8')
        from skills.watcher import _reload
        _reload()
        try:
            resp = _client_with_cookie('jane').post(
                f'/api/skills/{skill_name}/versions/20260501-regression-test/install',
                data=json.dumps({'target': 'LOCAL'}),
                content_type='application/json',
            )
            assert resp.status_code == 200, resp.content
            body = resp.json()
            expected = tmp_path / 'dst' / 'jane' / 'skills' / skill_name
            assert body['path'] == str(expected), (
                f"versioned install landed at {body['path']!r}, "
                f"should be at {str(expected)!r}"
            )
            assert expected.is_dir()
        finally:
            __import__('shutil').rmtree(ver_path, ignore_errors=True)
            _reload()
    else:
        skill_name, skill = versioned
        version = skill['versions'][0]['version']
        resp = _client_with_cookie('jane').post(
            f'/api/skills/{skill_name}/versions/{version}/install',
            data=json.dumps({'target': 'LOCAL'}),
            content_type='application/json',
        )
        assert resp.status_code == 200, resp.content
        body = resp.json()
        expected = tmp_path / 'dst' / 'jane' / 'skills' / skill_name
        assert body['path'] == str(expected)
        assert expected.is_dir()
