"""Fail-fast prod-config guards in skill_market/settings.py.

When DEBUG=False, the app must refuse to boot with:
  - missing SECRET_KEY
  - missing or '*' ALLOWED_HOSTS
  - missing or '*' CORS_ALLOWED_ORIGINS

When DEBUG=True, defaults stay developer-friendly.
"""
import importlib
import sys

import pytest


def _reload_settings():
    sys.modules.pop('skill_market.settings', None)
    return importlib.import_module('skill_market.settings')


def _clear_security_env(monkeypatch):
    for k in ('DEBUG', 'SECRET_KEY', 'ALLOWED_HOSTS', 'CORS_ALLOWED_ORIGINS'):
        monkeypatch.delenv(k, raising=False)


# ---------------------------------------------------------------------------
# DEBUG=False guards
# ---------------------------------------------------------------------------

def test_prod_requires_secret_key(monkeypatch):
    _clear_security_env(monkeypatch)
    monkeypatch.setenv('DEBUG', 'False')
    monkeypatch.setenv('ALLOWED_HOSTS', 'app.example.com')
    monkeypatch.setenv('CORS_ALLOWED_ORIGINS', 'https://app.example.com')
    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        _reload_settings()


def test_prod_rejects_missing_allowed_hosts(monkeypatch):
    _clear_security_env(monkeypatch)
    monkeypatch.setenv('DEBUG', 'False')
    monkeypatch.setenv('SECRET_KEY', 'x' * 50)
    monkeypatch.setenv('CORS_ALLOWED_ORIGINS', 'https://app.example.com')
    with pytest.raises(RuntimeError, match='ALLOWED_HOSTS'):
        _reload_settings()


def test_prod_rejects_wildcard_allowed_hosts(monkeypatch):
    _clear_security_env(monkeypatch)
    monkeypatch.setenv('DEBUG', 'False')
    monkeypatch.setenv('SECRET_KEY', 'x' * 50)
    monkeypatch.setenv('ALLOWED_HOSTS', '*')
    monkeypatch.setenv('CORS_ALLOWED_ORIGINS', 'https://app.example.com')
    with pytest.raises(RuntimeError, match='ALLOWED_HOSTS'):
        _reload_settings()


def test_prod_rejects_wildcard_cors(monkeypatch):
    _clear_security_env(monkeypatch)
    monkeypatch.setenv('DEBUG', 'False')
    monkeypatch.setenv('SECRET_KEY', 'x' * 50)
    monkeypatch.setenv('ALLOWED_HOSTS', 'app.example.com')
    monkeypatch.setenv('CORS_ALLOWED_ORIGINS', '*')
    with pytest.raises(RuntimeError, match='CORS_ALLOWED_ORIGINS'):
        _reload_settings()


def test_prod_with_all_explicit_values_boots(monkeypatch):
    _clear_security_env(monkeypatch)
    monkeypatch.setenv('DEBUG', 'False')
    monkeypatch.setenv('SECRET_KEY', 'x' * 50)
    monkeypatch.setenv('ALLOWED_HOSTS', 'app.example.com,api.example.com')
    monkeypatch.setenv('CORS_ALLOWED_ORIGINS', 'https://app.example.com')
    s = _reload_settings()
    assert s.DEBUG is False
    assert s.ALLOWED_HOSTS == ['app.example.com', 'api.example.com']
    assert s.CORS_ALLOWED_ORIGINS == 'https://app.example.com'


# ---------------------------------------------------------------------------
# DEBUG=True keeps developer-friendly defaults
# ---------------------------------------------------------------------------

def test_dev_defaults_boot_without_env(monkeypatch):
    _clear_security_env(monkeypatch)
    monkeypatch.setenv('DEBUG', 'True')
    s = _reload_settings()
    assert s.DEBUG is True
    assert s.SECRET_KEY
    assert s.ALLOWED_HOSTS == ['*']
    assert s.CORS_ALLOWED_ORIGINS == '*'


# ---------------------------------------------------------------------------
# INSTALL_TARGETS SSH config validation (C2 — block shell injection at boot)
# ---------------------------------------------------------------------------

import os as _os


def _clear_install_targets(monkeypatch):
    for k in list(_os.environ):
        if k.startswith('INSTALL_TARGET_'):
            monkeypatch.delenv(k, raising=False)


def _set_valid_ssh_target(monkeypatch):
    monkeypatch.setenv('INSTALL_TARGET_X_TYPE', 'ssh')
    monkeypatch.setenv('INSTALL_TARGET_X_BASE', '/srv/{user_name}/skills')
    monkeypatch.setenv('INSTALL_TARGET_X_HOST', 'host.example')
    monkeypatch.setenv('INSTALL_TARGET_X_USER', 'svc')
    monkeypatch.setenv('INSTALL_TARGET_X_SSH_KEY', '/etc/ssh/k')


def test_ssh_target_with_shell_meta_in_key_rejected(monkeypatch):
    _clear_install_targets(monkeypatch)
    _set_valid_ssh_target(monkeypatch)
    monkeypatch.setenv('INSTALL_TARGET_X_SSH_KEY', '/tmp/a;rm -rf /')
    with pytest.raises(RuntimeError, match='INSTALL_TARGET_X_SSH_KEY'):
        _reload_settings()


def test_ssh_target_with_space_in_key_rejected(monkeypatch):
    _clear_install_targets(monkeypatch)
    _set_valid_ssh_target(monkeypatch)
    monkeypatch.setenv('INSTALL_TARGET_X_SSH_KEY', '/tmp/has space.key')
    with pytest.raises(RuntimeError, match='INSTALL_TARGET_X_SSH_KEY'):
        _reload_settings()


def test_ssh_target_with_bad_host_rejected(monkeypatch):
    _clear_install_targets(monkeypatch)
    _set_valid_ssh_target(monkeypatch)
    monkeypatch.setenv('INSTALL_TARGET_X_HOST', 'host;evil')
    with pytest.raises(RuntimeError, match='INSTALL_TARGET_X_HOST'):
        _reload_settings()


def test_ssh_target_with_bad_user_rejected(monkeypatch):
    _clear_install_targets(monkeypatch)
    _set_valid_ssh_target(monkeypatch)
    monkeypatch.setenv('INSTALL_TARGET_X_USER', 'svc$')
    with pytest.raises(RuntimeError, match='INSTALL_TARGET_X_USER'):
        _reload_settings()


def test_ssh_target_missing_key_rejected(monkeypatch):
    _clear_install_targets(monkeypatch)
    monkeypatch.setenv('INSTALL_TARGET_X_TYPE', 'ssh')
    monkeypatch.setenv('INSTALL_TARGET_X_BASE', '/srv/{user_name}/skills')
    monkeypatch.setenv('INSTALL_TARGET_X_HOST', 'host.example')
    monkeypatch.setenv('INSTALL_TARGET_X_USER', 'svc')
    with pytest.raises(RuntimeError, match='INSTALL_TARGET_X_SSH_KEY'):
        _reload_settings()


def test_valid_ssh_target_boots(monkeypatch):
    _clear_install_targets(monkeypatch)
    _set_valid_ssh_target(monkeypatch)
    s = _reload_settings()
    assert s.INSTALL_TARGETS['X']['host'] == 'host.example'


def test_local_target_skips_ssh_validation(monkeypatch):
    _clear_install_targets(monkeypatch)
    monkeypatch.setenv('INSTALL_TARGET_L_TYPE', 'local')
    monkeypatch.setenv('INSTALL_TARGET_L_BASE', '/tmp/{user_name}/skills')
    s = _reload_settings()
    assert s.INSTALL_TARGETS['L']['type'] == 'local'
