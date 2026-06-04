import pytest

from skills.installer import InstallError


def test_install_error_carries_status_and_message():
    err = InstallError('bad target', http_status=400)
    assert str(err) == 'bad target'
    assert err.http_status == 400


def test_install_error_default_status_500():
    err = InstallError('boom')
    assert err.http_status == 500


from skills.installer import _validate_user_name, _resolve_target


def test_validate_user_name_accepts_alnum_dot_dash_underscore():
    _validate_user_name('jdoe')
    _validate_user_name('john.doe-2')
    _validate_user_name('A_B.C-1')


@pytest.mark.parametrize('bad', [
    '', '..', '../etc', 'a/b', 'a b', 'foo$', 'foo;rm', '\n', '\\\\path'])
def test_validate_user_name_rejects_traversal_and_specials(bad):
    with pytest.raises(InstallError) as exc:
        _validate_user_name(bad)
    assert exc.value.http_status == 400


def test_resolve_target_returns_config(settings):
    settings.INSTALL_TARGETS = {
        'F12': {'type': 'local', 'base': '/tmp/{user_name}/skills'},
    }
    cfg = _resolve_target('F12')
    assert cfg['type'] == 'local'


def test_resolve_target_unknown_raises_400(settings):
    settings.INSTALL_TARGETS = {}
    with pytest.raises(InstallError) as exc:
        _resolve_target('F99')
    assert exc.value.http_status == 400
    assert 'F99' in str(exc.value)


from skills.installer import install_skill


def _make_src(tmp_path, name='git-workflow'):
    src = tmp_path / 'repo' / name
    src.mkdir(parents=True)
    (src / 'SKILL.md').write_text('---\nname: git-workflow\n---\nbody', encoding='utf-8')
    (src / 'extra.txt').write_text('hello', encoding='utf-8')
    return str(src)


def test_install_local_copies_dir(tmp_path, settings):
    src = _make_src(tmp_path)
    base = tmp_path / 'dst' / '{user_name}' / 'skills'
    settings.INSTALL_TARGETS = {
        'LOCAL': {'type': 'local', 'base': str(base)},
    }

    result = install_skill(src, 'LOCAL', 'jdoe')

    expected = tmp_path / 'dst' / 'jdoe' / 'skills' / 'git-workflow'
    assert expected.is_dir()
    assert (expected / 'SKILL.md').read_text(encoding='utf-8') == '---\nname: git-workflow\n---\nbody'
    assert (expected / 'extra.txt').read_text(encoding='utf-8') == 'hello'
    assert result == {'target': 'LOCAL', 'path': str(expected)}


def test_install_local_overwrites_and_deletes_stale(tmp_path, settings):
    src = _make_src(tmp_path)
    base = tmp_path / 'dst' / '{user_name}' / 'skills'
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': str(base)}}

    # Pre-populate the target with a stale file that should be removed.
    stale_dir = tmp_path / 'dst' / 'jdoe' / 'skills' / 'git-workflow'
    stale_dir.mkdir(parents=True)
    (stale_dir / 'OLD.md').write_text('old', encoding='utf-8')

    install_skill(src, 'LOCAL', 'jdoe')

    assert not (stale_dir / 'OLD.md').exists()
    assert (stale_dir / 'SKILL.md').exists()


def test_install_local_rejects_bad_user_name(tmp_path, settings):
    src = _make_src(tmp_path)
    settings.INSTALL_TARGETS = {
        'LOCAL': {'type': 'local', 'base': str(tmp_path / '{user_name}')},
    }
    with pytest.raises(InstallError) as exc:
        install_skill(src, 'LOCAL', '../etc')
    assert exc.value.http_status == 400


import subprocess
from unittest.mock import MagicMock


def test_install_ssh_invokes_rsync_with_expected_args(tmp_path, settings, monkeypatch):
    src = _make_src(tmp_path)
    settings.INSTALL_TARGETS = {
        'F15': {
            'type': 'ssh',
            'base': '/AAA/{user_name}/skills',
            'host': 'f15.example',
            'user': 'svc',
            'ssh_key': '/etc/ssh/k',
        },
    }
    settings.INSTALL_TIMEOUT_SECONDS = 60

    captured = {}

    def fake_run(cmd, **kwargs):
        captured['cmd'] = cmd
        captured['kwargs'] = kwargs
        return MagicMock(returncode=0, stderr=b'', stdout=b'')

    monkeypatch.setattr('skills.installer.subprocess.run', fake_run)

    result = install_skill(src, 'F15', 'jdoe')

    cmd = captured['cmd']
    assert cmd[0] == 'rsync'
    assert '-a' in cmd
    assert '--delete' in cmd
    assert '-e' in cmd
    e_idx = cmd.index('-e')
    ssh_str = cmd[e_idx + 1]
    assert 'ssh' in ssh_str
    assert '-i /etc/ssh/k' in ssh_str
    assert 'BatchMode=yes' in ssh_str

    # Source must end with trailing slash so contents (not the dir itself) go into dst.
    assert cmd[-2].rstrip('/').endswith('git-workflow')
    assert cmd[-2].endswith('/')
    # Dest is user@host:/path/skill_name/
    assert cmd[-1] == 'svc@f15.example:/AAA/jdoe/skills/git-workflow/'

    assert captured['kwargs']['timeout'] == 60
    assert captured['kwargs']['check'] is True
    assert captured['kwargs']['capture_output'] is True

    assert result == {'target': 'F15', 'path': '/AAA/jdoe/skills/git-workflow'}


def test_install_ssh_propagates_rsync_failure(tmp_path, settings, monkeypatch):
    src = _make_src(tmp_path)
    settings.INSTALL_TARGETS = {
        'F15': {
            'type': 'ssh', 'base': '/AAA/{user_name}/skills',
            'host': 'h', 'user': 'u', 'ssh_key': '/k',
        },
    }
    settings.INSTALL_TIMEOUT_SECONDS = 60

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=23, cmd=cmd, output=b'', stderr=b'rsync: connection refused')

    monkeypatch.setattr('skills.installer.subprocess.run', fake_run)

    with pytest.raises(InstallError) as exc:
        install_skill(src, 'F15', 'jdoe')
    assert exc.value.http_status == 502
    assert 'connection refused' in str(exc.value)


def test_install_ssh_timeout_raises_504(tmp_path, settings, monkeypatch):
    src = _make_src(tmp_path)
    settings.INSTALL_TARGETS = {
        'F15': {
            'type': 'ssh', 'base': '/AAA/{user_name}/skills',
            'host': 'h', 'user': 'u', 'ssh_key': '/k',
        },
    }
    settings.INSTALL_TIMEOUT_SECONDS = 5

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)

    monkeypatch.setattr('skills.installer.subprocess.run', fake_run)

    with pytest.raises(InstallError) as exc:
        install_skill(src, 'F15', 'jdoe')
    assert exc.value.http_status == 504
    assert 'timed out' in str(exc.value).lower()


def test_install_local_logs_request_and_success(tmp_path, caplog):
    import logging
    from unittest.mock import patch
    src = tmp_path / 'myskill'
    src.mkdir()
    (src / 'SKILL.md').write_text('---\nname: myskill\n---\n')
    dst_base = tmp_path / 'dest'

    targets = {'LOCAL': {'type': 'local', 'base': str(dst_base / '{user_name}')}}
    with patch.object(__import__('django.conf', fromlist=['settings']).settings, 'INSTALL_TARGETS', targets):
        # Enable propagation on the 'skills' parent so caplog (which hooks the
        # root logger) can capture records even though settings.py sets
        # propagate=False on the skills logger.
        import logging as _logging
        skills_logger = _logging.getLogger('skills')
        orig_propagate = skills_logger.propagate
        skills_logger.propagate = True
        try:
            with caplog.at_level(logging.INFO, logger='skills.installer'):
                install_skill(str(src), 'LOCAL', 'alice')
        finally:
            skills_logger.propagate = orig_propagate

    assert 'install requested' in caplog.text
    assert 'install success' in caplog.text
    assert 'myskill' in caplog.text


def test_install_local_logs_error_on_failure(tmp_path, caplog):
    import logging
    import pytest
    from unittest.mock import patch
    src = tmp_path / 'myskill'
    # intentionally NOT creating src — triggers InstallError (source not found)
    dst_base = tmp_path / 'dest'

    targets = {'LOCAL': {'type': 'local', 'base': str(dst_base / '{user_name}')}}
    with patch.object(__import__('django.conf', fromlist=['settings']).settings, 'INSTALL_TARGETS', targets):
        # Enable propagation on the 'skills' parent so caplog (which hooks the
        # root logger) can capture records even though settings.py sets
        # propagate=False on the skills logger.
        import logging as _logging
        skills_logger = _logging.getLogger('skills')
        orig_propagate = skills_logger.propagate
        skills_logger.propagate = True
        try:
            with caplog.at_level(logging.ERROR, logger='skills.installer'):
                with pytest.raises(InstallError):
                    install_skill(str(src), 'LOCAL', 'alice')
        finally:
            skills_logger.propagate = orig_propagate

    assert 'install failed' in caplog.text
