import os
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from django.test import override_settings

from skills.installer import (
    InstallError,
    _validate_skill_name,
    uninstall_skill,
)
from skills import envelope as e


def test_validate_skill_name_accepts_normal_names():
    _validate_skill_name('coding-guide')
    _validate_skill_name('webapp_testing')
    _validate_skill_name('skill.v2')
    _validate_skill_name('A-Bc_1.2')


@pytest.mark.parametrize('bad', [
    '',
    '..',
    '.',
    '...',
    '../etc',
    'a/b',
    'a\\b',
    'has space',
    'has;semi',
    'has$dollar',
    'has`backtick',
])
def test_validate_skill_name_rejects_traversal_and_specials(bad):
    with pytest.raises(InstallError) as ex:
        _validate_skill_name(bad)
    assert ex.value.http_status == 400
    assert ex.value.code == e.UNINSTALL_SKILL_NAME_INVALID


def test_uninstall_skill_local_removes_directory(tmp_path):
    base = tmp_path / 'coman' / 'skills'
    base.mkdir(parents=True)
    target = base / 'coding-guide'
    target.mkdir()
    (target / 'SKILL.md').write_text('---\nname: coding-guide\n---\n')

    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    with override_settings(INSTALL_TARGETS={'TEST': cfg}):
        result = uninstall_skill('TEST', 'coman', 'coding-guide')

    assert result == {'target': 'TEST', 'path': str(target)}
    assert not target.exists()
    assert base.exists()


def test_uninstall_skill_local_missing_path_returns_404(tmp_path):
    base = tmp_path / 'coman' / 'skills'
    base.mkdir(parents=True)
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    with override_settings(INSTALL_TARGETS={'TEST': cfg}):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('TEST', 'coman', 'does-not-exist')
    assert ex.value.http_status == 404
    assert ex.value.code == e.UNINSTALL_TARGET_PATH_NOT_FOUND


def test_uninstall_skill_refuses_symlink(tmp_path):
    base = tmp_path / 'coman' / 'skills'
    base.mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'sentinel').write_text('keep-me')

    link = base / 'evil'
    try:
        os.symlink(str(outside), str(link))
    except (OSError, NotImplementedError):
        pytest.skip('symlink unsupported')

    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    with override_settings(INSTALL_TARGETS={'TEST': cfg}):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('TEST', 'coman', 'evil')
    assert ex.value.http_status == 409
    assert (outside / 'sentinel').exists()


def test_uninstall_skill_invalid_user_rejected(tmp_path):
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    with override_settings(INSTALL_TARGETS={'TEST': cfg}):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('TEST', '..', 'coding-guide')
    assert ex.value.http_status == 400


def test_uninstall_skill_invalid_skill_name_rejected(tmp_path):
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    with override_settings(INSTALL_TARGETS={'TEST': cfg}):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('TEST', 'coman', '../etc')
    assert ex.value.http_status == 400


def test_uninstall_skill_unknown_target():
    with override_settings(INSTALL_TARGETS={}):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('NOPE', 'coman', 'coding-guide')
    assert ex.value.http_status == 400


def _ssh_target_cfg():
    return {
        'type': 'ssh',
        'base': '/AAA/{user_name}/skills',
        'host': 'f15.intra.example',
        'user': 'svc-skillmarket',
        'ssh_key': '/etc/ssh/skillmarket_id_rsa',
    }


def test_uninstall_skill_ssh_invokes_rm_with_quoted_path():
    completed = MagicMock(returncode=0, stdout=b'', stderr=b'')
    with override_settings(INSTALL_TARGETS={'F15': _ssh_target_cfg()}), \
         patch('skills.installer.subprocess.run', return_value=completed) as run:
        result = uninstall_skill('F15', 'coman', 'coding-guide')

    assert result == {
        'target': 'F15',
        'path': '/AAA/coman/skills/coding-guide',
    }
    args, _kwargs = run.call_args
    cmd = args[0]
    assert cmd[0] == 'ssh'
    assert 'BatchMode=yes' in ' '.join(cmd)
    remote_cmd = cmd[-1]
    assert remote_cmd.startswith('rm -rf -- ')
    assert '/AAA/coman/skills/coding-guide' in remote_cmd


def test_uninstall_skill_ssh_nonzero_exit_raises_500():
    err = subprocess.CalledProcessError(1, 'ssh', stderr=b'rm: cannot remove')
    with override_settings(INSTALL_TARGETS={'F15': _ssh_target_cfg()}), \
         patch('skills.installer.subprocess.run', side_effect=err):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('F15', 'coman', 'coding-guide')
    assert ex.value.http_status == 500
    assert ex.value.code == e.UNINSTALL_FAILED


def test_uninstall_skill_ssh_timeout_raises_504():
    err = subprocess.TimeoutExpired(cmd='ssh', timeout=10)
    with override_settings(INSTALL_TARGETS={'F15': _ssh_target_cfg()}), \
         patch('skills.installer.subprocess.run', side_effect=err):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('F15', 'coman', 'coding-guide')
    assert ex.value.http_status == 504


def test_uninstall_skill_ssh_missing_host_raises_500():
    cfg = _ssh_target_cfg()
    cfg['host'] = ''
    with override_settings(INSTALL_TARGETS={'F15': cfg}):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('F15', 'coman', 'coding-guide')
    assert ex.value.http_status == 500
