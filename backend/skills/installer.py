"""Skill install transport (local copy + ssh rsync).

Single entry point: install_skill(src_dir, target_name, user_name).
Raises InstallError(message, http_status) on any failure; views.py maps
the http_status straight onto the JSON response.
"""
import os
import re
import shutil
import subprocess

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


def install_skill(src_dir, target_name, user_name):
    """Install a skill directory to a configured target.

    Returns: {'target': str, 'path': str}
    Raises: InstallError(..., http_status=...)
    """
    _validate_user_name(user_name)
    cfg = _resolve_target(target_name)

    skill_name = os.path.basename(os.path.normpath(src_dir))
    if not skill_name:
        raise InstallError(f'Cannot derive skill name from src_dir: {src_dir!r}')

    base_template = cfg.get('base')
    if not base_template:
        raise InstallError(
            f"Target {target_name!r} missing 'base' config",
            http_status=500,
        )
    base = base_template.format(user_name=user_name).rstrip('/\\')
    dst = os.path.join(base, skill_name)

    ttype = cfg.get('type')
    if ttype == 'local':
        _install_local(src_dir, dst)
    elif ttype == 'ssh':
        _install_ssh(src_dir, dst, cfg)
    else:
        raise InstallError(
            f"Target {target_name!r} has unsupported type {ttype!r}",
            http_status=500,
        )

    return {'target': target_name, 'path': dst}


def _install_local(src_dir, dst):
    if not os.path.isdir(src_dir):
        raise InstallError(f'Source not found: {src_dir}', http_status=404)
    parent = os.path.dirname(dst)
    os.makedirs(parent, exist_ok=True)
    if os.path.exists(dst):
        shutil.rmtree(dst, ignore_errors=False)
    shutil.copytree(src_dir, dst)


def _install_ssh(src_dir, dst, cfg):
    if not os.path.isdir(src_dir):
        raise InstallError(f'Source not found: {src_dir}', http_status=404)

    for required in ('host', 'user', 'ssh_key'):
        if not cfg.get(required):
            raise InstallError(
                f"SSH target missing required field {required!r}",
                http_status=500,
            )

    ssh_cmd = (
        f"ssh -i {cfg['ssh_key']} -o BatchMode=yes "
        f"-o StrictHostKeyChecking=accept-new"
    )
    src_arg = src_dir.rstrip('/\\') + '/'
    dst_arg = f"{cfg['user']}@{cfg['host']}:{dst}/"

    cmd = ['rsync', '-a', '--delete', '-e', ssh_cmd, src_arg, dst_arg]

    try:
        subprocess.run(
            cmd,
            timeout=settings.INSTALL_TIMEOUT_SECONDS,
            check=True,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        raise InstallError(
            f'Install timed out after {settings.INSTALL_TIMEOUT_SECONDS}s',
            http_status=504,
        )
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b'').decode('utf-8', errors='replace')[:500].strip()
        raise InstallError(
            f'rsync failed (exit {e.returncode}): {stderr}',
            http_status=502,
        )
