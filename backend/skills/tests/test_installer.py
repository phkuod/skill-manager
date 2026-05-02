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
