"""Skill install transport (local copy + ssh rsync).

Single entry point: install_skill(src_dir, target_name, user_name).
Raises InstallError(message, http_status) on any failure; views.py maps
the http_status straight onto the JSON response.
"""
import logging
import os
import re
import shutil
import subprocess
import time

from django.conf import settings

logger = logging.getLogger('skills.installer')


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


def install_skill(src_dir, target_name, user_name, skill_name=None):
    """Install a skill directory to a configured target.

    skill_name controls the destination directory name. When installing a
    versioned skill, src_dir points at the dated subdir (e.g.
    `.../algorithmic-art/20260501-foo`) but the install must still land at
    `<base>/algorithmic-art` so downstream tools resolve it by canonical name.
    Pass skill_name explicitly in that case. When omitted, the basename of
    src_dir is used.

    Returns: {'target': str, 'path': str}
    Raises: InstallError(..., http_status=...)
    """
    _validate_user_name(user_name)
    cfg = _resolve_target(target_name)

    if skill_name is None:
        skill_name = os.path.basename(os.path.normpath(src_dir))
    if not skill_name:
        raise InstallError(f'Cannot derive skill name from src_dir: {src_dir!r}')

    base_template = cfg.get('base')
    if not base_template:
        raise InstallError(
            f"Target {target_name!r} missing 'base' config",
            http_status=500,
        )
    ttype = cfg.get('type')
    base = base_template.format(user_name=user_name).rstrip('/\\')
    if ttype == 'ssh':
        dst = base.replace('\\', '/') + '/' + skill_name
    else:
        dst = os.path.join(base, skill_name)

    logger.info('install requested: skill=%s user=%s target=%s', skill_name, user_name, target_name)
    t0 = time.monotonic()

    try:
        if ttype == 'local':
            _install_local(src_dir, dst)
        elif ttype == 'ssh':
            _install_ssh(src_dir, dst, cfg)
        else:
            raise InstallError(
                f"Target {target_name!r} has unsupported type {ttype!r}",
                http_status=500,
            )
    except InstallError as exc:
        logger.error('install failed: skill=%s user=%s target=%s — %s', skill_name, user_name, target_name, exc)
        raise

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info('install success: skill=%s → %s (%dms)', skill_name, dst, elapsed)
    return {'target': target_name, 'path': dst}


def _install_local(src_dir, dst):
    if not os.path.isdir(src_dir):
        raise InstallError(f'Source not found: {src_dir}', http_status=404)
    parent = os.path.dirname(dst)
    os.makedirs(parent, exist_ok=True)
    if os.path.exists(dst):
        shutil.rmtree(dst, ignore_errors=False)
    _version_pattern = re.compile(r'^(\d{8})(?:-.*)?$')

    def _ignore_versions(directory, contents):
        if os.path.normpath(directory) != os.path.normpath(src_dir):
            return []
        return [
            name for name in contents
            if _version_pattern.match(name)
            and os.path.isfile(os.path.join(directory, name, 'SKILL.md'))
        ]

    shutil.copytree(src_dir, dst, ignore=_ignore_versions)


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
