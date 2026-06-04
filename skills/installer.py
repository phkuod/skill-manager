"""Skill install transport (local copy + ssh rsync).

Single entry point: install_skill(src_dir, target_name, user_name).
Raises InstallError(message, http_status, code) on any failure; legacy
views.py maps http_status onto the JSON response, while v1 views_v1.py
maps the structured `code` onto the {error: {code, message}} envelope.
"""
import logging
import os
import re
import shlex
import shutil
import subprocess
import time

from django.conf import settings

from . import envelope as e

logger = logging.getLogger('skills.installer')


class InstallError(Exception):
    def __init__(self, message, http_status=500, code=None):
        super().__init__(message)
        self.http_status = http_status
        self.code = code or e.INSTALL_FAILED


_user_name_re = re.compile(r'^[A-Za-z0-9_.-]+$')


def _validate_user_name(user_name):
    if not user_name or not _user_name_re.match(user_name) or set(user_name) <= {'.'}:
        raise InstallError(
            f'Invalid user_name: {user_name!r}. Must match [A-Za-z0-9_.-]+.',
            http_status=400,
            code=e.INSTALL_USERNAME_INVALID,
        )


_skill_name_re = re.compile(r'^[A-Za-z0-9_.-]+$')


def _validate_skill_name(skill_name):
    if (
        not skill_name
        or not _skill_name_re.match(skill_name)
        or set(skill_name) <= {'.'}
    ):
        raise InstallError(
            f'Invalid skill_name: {skill_name!r}. Must match [A-Za-z0-9_.-]+.',
            http_status=400,
            code=e.UNINSTALL_SKILL_NAME_INVALID,
        )


def _ensure_inside_base(dst, base):
    """Resolve dst with realpath and verify it stays under base.

    Shared by _install_local and _uninstall_local. Raises
    InstallError(http_status=409) on escape, missing base, or resolve failure.
    """
    try:
        base_real = os.path.realpath(base)
        dst_real = os.path.realpath(dst)
        common = os.path.commonpath([dst_real, base_real])
    except (ValueError, OSError) as exc:
        raise InstallError(
            f'Path resolution failed: {exc}',
            http_status=409,
            code=e.UNINSTALL_PATH_OUTSIDE_BASE,
        )

    if common != base_real or dst_real == base_real:
        raise InstallError(
            f'Resolved path escapes target base: {dst_real}',
            http_status=409,
            code=e.UNINSTALL_PATH_OUTSIDE_BASE,
        )


def _resolve_target(target_name):
    cfg = settings.INSTALL_TARGETS.get(target_name)
    if cfg is None:
        raise InstallError(
            f"Unknown install target: {target_name!r}. Configured: "
            f"{sorted(settings.INSTALL_TARGETS.keys())}",
            http_status=400,
            code=e.INSTALL_TARGET_INVALID,
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
        raise InstallError(
            f'Cannot derive skill name from src_dir: {src_dir!r}',
            code=e.INSTALL_FAILED,
        )

    base_template = cfg.get('base')
    if not base_template:
        raise InstallError(
            f"Target {target_name!r} missing 'base' config",
            http_status=500,
            code=e.INSTALL_CONFIG_ERROR,
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
            _install_local(src_dir, dst, base)
        elif ttype == 'ssh':
            _install_ssh(src_dir, dst, cfg)
        else:
            raise InstallError(
                f"Target {target_name!r} has unsupported type {ttype!r}",
                http_status=500,
                code=e.INSTALL_CONFIG_ERROR,
            )
    except InstallError as exc:
        logger.error('install failed: skill=%s user=%s target=%s — %s', skill_name, user_name, target_name, exc)
        raise

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info('install success: skill=%s → %s (%dms)', skill_name, dst, elapsed)
    return {'target': target_name, 'path': dst}


def _install_local(src_dir, dst, base):
    if not os.path.isdir(src_dir):
        raise InstallError(
            f'Source not found: {src_dir}',
            http_status=404,
            code=e.INSTALL_SOURCE_NOT_FOUND,
        )
    parent = os.path.dirname(dst)
    os.makedirs(parent, exist_ok=True)
    # After parent is materialized (so realpath can resolve symlinks on it),
    # verify the destination stays inside the configured base.
    _ensure_inside_base(dst, base)
    if os.path.exists(dst):
        shutil.rmtree(dst, ignore_errors=False)
    _version_pattern = re.compile(r'^(\d{8})-.+$')

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
        raise InstallError(
            f'Source not found: {src_dir}',
            http_status=404,
            code=e.INSTALL_SOURCE_NOT_FOUND,
        )

    for required in ('host', 'user', 'ssh_key'):
        if not cfg.get(required):
            raise InstallError(
                f"SSH target missing required field {required!r}",
                http_status=500,
                code=e.INSTALL_CONFIG_ERROR,
            )

    ssh_cmd = (
        f"ssh -i {shlex.quote(cfg['ssh_key'])} -o BatchMode=yes "
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
            code=e.RSYNC_TIMEOUT,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b'').decode('utf-8', errors='replace')[:500].strip()
        raise InstallError(
            f'rsync failed (exit {exc.returncode}): {stderr}',
            http_status=502,
            code=e.RSYNC_FAILED,
        )


def uninstall_skill(target_name, user_name, skill_name):
    """Remove a previously-installed skill directory from a target.

    Validates inputs, resolves the target, verifies the path stays inside
    the configured base, then deletes (local) or sends a remote rm via SSH.

    Returns: {'target': str, 'path': str}
    Raises: InstallError(..., http_status=...)
    """
    _validate_user_name(user_name)
    _validate_skill_name(skill_name)
    cfg = _resolve_target(target_name)

    base_template = cfg.get('base')
    if not base_template:
        raise InstallError(
            f"Target {target_name!r} missing 'base' config",
            http_status=500,
            code=e.INSTALL_CONFIG_ERROR,
        )

    ttype = cfg.get('type')
    base = base_template.format(user_name=user_name).rstrip('/\\')
    if ttype == 'ssh':
        dst = base.replace('\\', '/') + '/' + skill_name
    else:
        dst = os.path.join(base, skill_name)

    logger.info('uninstall requested: skill=%s user=%s target=%s', skill_name, user_name, target_name)
    t0 = time.monotonic()

    try:
        if ttype == 'local':
            _uninstall_local(dst, base)
        elif ttype == 'ssh':
            _uninstall_ssh(cfg, dst, base)
        else:
            raise InstallError(
                f"Target {target_name!r} has unsupported type {ttype!r}",
                http_status=500,
                code=e.INSTALL_CONFIG_ERROR,
            )
    except InstallError as exc:
        logger.error('uninstall failed: skill=%s user=%s target=%s — %s', skill_name, user_name, target_name, exc)
        raise

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info('uninstall success: %s (%dms)', dst, elapsed)
    return {'target': target_name, 'path': dst}


def _uninstall_local(dst, base):
    """Local removal. Refuses symlinks, enforces path stays inside base."""
    if os.path.islink(dst):
        raise InstallError(
            f'Refusing to delete symlink: {dst}',
            http_status=409,
            code=e.UNINSTALL_PATH_OUTSIDE_BASE,
        )

    if not os.path.exists(dst):
        raise InstallError(
            f'Target path does not exist: {dst}',
            http_status=404,
            code=e.UNINSTALL_TARGET_PATH_NOT_FOUND,
        )

    _ensure_inside_base(dst, base)

    try:
        shutil.rmtree(dst)
    except OSError as exc:
        raise InstallError(
            f'rmtree failed: {exc}',
            http_status=500,
            code=e.UNINSTALL_FAILED,
        )


def _uninstall_ssh(cfg, dst, base):
    """SSH removal. Path-traversal guard via prefix check on POSIX strings."""
    base_norm = base.replace('\\', '/').rstrip('/')
    dst_norm = dst.replace('\\', '/').rstrip('/')
    if not dst_norm.startswith(base_norm + '/') or dst_norm == base_norm:
        raise InstallError(
            f'Resolved path escapes target base: {dst_norm}',
            http_status=409,
            code=e.UNINSTALL_PATH_OUTSIDE_BASE,
        )
    if '..' in dst_norm.split('/'):
        raise InstallError(
            f'Path contains traversal segment: {dst_norm}',
            http_status=409,
            code=e.UNINSTALL_PATH_OUTSIDE_BASE,
        )

    for required in ('host', 'user', 'ssh_key'):
        if not cfg.get(required):
            raise InstallError(
                f"SSH target missing required field {required!r}",
                http_status=500,
                code=e.INSTALL_CONFIG_ERROR,
            )

    remote_cmd = f'rm -rf -- {shlex.quote(dst_norm)}'
    ssh_cmd = [
        'ssh',
        '-i', cfg['ssh_key'],
        '-o', 'BatchMode=yes',
        '-o', 'ConnectTimeout=10',
        '-o', 'StrictHostKeyChecking=accept-new',
        f"{cfg['user']}@{cfg['host']}",
        remote_cmd,
    ]

    try:
        subprocess.run(
            ssh_cmd,
            timeout=settings.INSTALL_TIMEOUT_SECONDS,
            check=True,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        raise InstallError(
            f'Uninstall timed out after {settings.INSTALL_TIMEOUT_SECONDS}s',
            http_status=504,
            code=e.UNINSTALL_FAILED,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b'').decode('utf-8', errors='replace')[:500].strip()
        raise InstallError(
            f'ssh rm failed (exit {exc.returncode}): {stderr}',
            http_status=500,
            code=e.UNINSTALL_FAILED,
        )
