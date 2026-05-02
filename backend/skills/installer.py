"""Skill install transport (local copy + ssh rsync).

Single entry point: install_skill(src_dir, target_name, user_name).
Raises InstallError(message, http_status) on any failure; views.py maps
the http_status straight onto the JSON response.
"""
import re

from django.conf import settings


class InstallError(Exception):
    def __init__(self, message, http_status=500):
        super().__init__(message)
        self.http_status = http_status


_user_name_re = re.compile(r'^[A-Za-z0-9_.-]+$')


def _validate_user_name(user_name):
    if not user_name or not _user_name_re.match(user_name) or set(user_name) <= {'.'}:
        raise InstallError(
            f'Invalid user_name: {user_name!r}. Must match [A-Za-z0-9_.-]+.',
            http_status=400,
        )


def _resolve_target(target_name):
    cfg = settings.INSTALL_TARGETS.get(target_name)
    if cfg is None:
        raise InstallError(
            f"Unknown install target: {target_name!r}. Configured: "
            f"{sorted(settings.INSTALL_TARGETS.keys())}",
            http_status=400,
        )
    return cfg
