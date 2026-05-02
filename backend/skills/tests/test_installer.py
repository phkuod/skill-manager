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
