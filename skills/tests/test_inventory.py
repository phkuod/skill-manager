import os

import pytest

from skills.inventory import (
    InventoryError,
    _list_local,
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
