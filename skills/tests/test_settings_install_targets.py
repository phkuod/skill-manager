import importlib
import os
import sys


def _reload_settings():
    """Re-import settings with current os.environ.

    settings.py runs at import time, so we drop it from sys.modules and
    re-import to pick up env changes. test_settings.* env vars set via
    monkeypatch.setenv are applied before reload.
    """
    sys.modules.pop('skill_market.settings', None)
    return importlib.import_module('skill_market.settings')


def test_install_targets_parses_grouped_env_vars(monkeypatch):
    monkeypatch.setenv('INSTALL_TARGET_F12_TYPE', 'local')
    monkeypatch.setenv('INSTALL_TARGET_F12_BASE', '/tmp/{user_name}/skills')
    monkeypatch.setenv('INSTALL_TARGET_F15_TYPE', 'ssh')
    monkeypatch.setenv('INSTALL_TARGET_F15_BASE', '/AAA/{user_name}/skills')
    monkeypatch.setenv('INSTALL_TARGET_F15_HOST', 'f15.example')
    monkeypatch.setenv('INSTALL_TARGET_F15_USER', 'svc')
    monkeypatch.setenv('INSTALL_TARGET_F15_SSH_KEY', '/etc/ssh/k')

    s = _reload_settings()

    assert s.INSTALL_TARGETS['F12'] == {
        'type': 'local',
        'base': '/tmp/{user_name}/skills',
    }
    assert s.INSTALL_TARGETS['F15'] == {
        'type': 'ssh',
        'base': '/AAA/{user_name}/skills',
        'host': 'f15.example',
        'user': 'svc',
        'ssh_key': '/etc/ssh/k',
    }


def test_install_timeout_default_60(monkeypatch):
    monkeypatch.delenv('INSTALL_TIMEOUT_SECONDS', raising=False)
    s = _reload_settings()
    assert s.INSTALL_TIMEOUT_SECONDS == 60


def test_install_timeout_override(monkeypatch):
    monkeypatch.setenv('INSTALL_TIMEOUT_SECONDS', '120')
    s = _reload_settings()
    assert s.INSTALL_TIMEOUT_SECONDS == 120


def test_install_targets_empty_when_no_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith('INSTALL_TARGET_'):
            monkeypatch.delenv(k, raising=False)
    s = _reload_settings()
    assert s.INSTALL_TARGETS == {}
