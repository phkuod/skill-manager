import pytest

from skills.installer import InstallError


def test_install_error_carries_status_and_message():
    err = InstallError('bad target', http_status=400)
    assert str(err) == 'bad target'
    assert err.http_status == 400


def test_install_error_default_status_500():
    err = InstallError('boom')
    assert err.http_status == 500
