import os
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from skills.inventory import (
    InventoryError,
    _list_local,
    _list_ssh,
)
from skills import envelope as e


def test_list_local_returns_directories(tmp_path):
    (tmp_path / 'alpha').mkdir()
    (tmp_path / 'beta').mkdir()
    (tmp_path / 'a_file.txt').write_text('hi')

    rows = _list_local(str(tmp_path))
    names = sorted(r[0] for r in rows)

    assert names == ['alpha', 'beta']
    for name, path, mtime in rows:
        assert path == os.path.join(str(tmp_path), name)
        assert isinstance(mtime, float)


def test_list_local_missing_base_returns_empty(tmp_path):
    nonexistent = str(tmp_path / 'does-not-exist')
    assert _list_local(nonexistent) == []


def test_list_local_skips_files_and_symlinks_to_dirs(tmp_path):
    (tmp_path / 'real').mkdir()
    (tmp_path / 'file.txt').write_text('x')
    try:
        os.symlink(str(tmp_path / 'real'), str(tmp_path / 'link'))
    except (OSError, NotImplementedError):
        pytest.skip('symlink unsupported on this platform')

    rows = _list_local(str(tmp_path))
    names = sorted(r[0] for r in rows)
    assert names == ['real']


def _ssh_cfg():
    return {
        'host': 'f15.intra.example',
        'user': 'svc-skillmarket',
        'ssh_key': '/etc/ssh/skillmarket_id_rsa',
    }


def test_list_ssh_parses_find_output():
    fake_stdout = b'coding-guide\t1715245391.0000000000\nlegacy-thing\t1722500000.5000000000\n'
    completed = MagicMock(returncode=0, stdout=fake_stdout, stderr=b'')

    with patch('skills.inventory.subprocess.run', return_value=completed) as run:
        rows = _list_ssh(_ssh_cfg(), '/AAA/coman/skills')

    args, kwargs = run.call_args
    cmd = args[0]
    assert cmd[0] == 'ssh'
    assert '-i' in cmd and '/etc/ssh/skillmarket_id_rsa' in cmd
    assert 'BatchMode=yes' in ' '.join(cmd)
    assert "'/AAA/coman/skills'" in cmd[-1] or '"/AAA/coman/skills"' in cmd[-1]

    names = sorted(r[0] for r in rows)
    assert names == ['coding-guide', 'legacy-thing']
    paths = {r[0]: r[1] for r in rows}
    assert paths['coding-guide'] == '/AAA/coman/skills/coding-guide'
    mtimes = {r[0]: r[2] for r in rows}
    assert mtimes['coding-guide'] == pytest.approx(1715245391.0)


def test_list_ssh_empty_output_returns_empty_list():
    completed = MagicMock(returncode=0, stdout=b'', stderr=b'')
    with patch('skills.inventory.subprocess.run', return_value=completed):
        assert _list_ssh(_ssh_cfg(), '/AAA/coman/skills') == []


def test_list_ssh_nonzero_exit_raises():
    err = subprocess.CalledProcessError(255, 'ssh', stderr=b'Permission denied')
    with patch('skills.inventory.subprocess.run', side_effect=err):
        with pytest.raises(InventoryError) as ex:
            _list_ssh(_ssh_cfg(), '/AAA/coman/skills')
    assert ex.value.http_status == 502


def test_list_ssh_timeout_raises():
    err = subprocess.TimeoutExpired(cmd='ssh', timeout=10)
    with patch('skills.inventory.subprocess.run', side_effect=err):
        with pytest.raises(InventoryError) as ex:
            _list_ssh(_ssh_cfg(), '/AAA/coman/skills')
    assert ex.value.http_status == 504


def test_list_ssh_missing_config_raises():
    with pytest.raises(InventoryError) as ex:
        _list_ssh({'host': '', 'user': '', 'ssh_key': ''}, '/AAA/coman/skills')
    assert ex.value.http_status == 500
