"""Read-only skill inventory.

Scans an install target's base directory and returns the list of
top-level directories present (each presumed to be an installed skill).
Local targets use scandir; SSH targets use a single `find` round trip.

The orchestrator `list_installed_skills` cross-references entries with
the in-memory catalog from skills.watcher and partitions them into
`catalog` (matched) and `orphan` (unmatched) groups.

Raises InventoryError(message, http_status, code) on any failure.
The views layer maps http_status onto the legacy JSON response and
code onto the v1 envelope.
"""
import logging
import os
import shlex
import subprocess
from datetime import datetime, timezone

from django.conf import settings

from . import envelope as e
from .installer import _validate_user_name, InstallError
from .watcher import get_skills

logger = logging.getLogger('skills.inventory')


class InventoryError(Exception):
    def __init__(self, message, http_status=500, code=None):
        super().__init__(message)
        self.http_status = http_status
        self.code = code or e.INVENTORY_FAILED


def _list_local(base):
    """Return [(name, abs_path, mtime_epoch), ...] for directories in base.

    Skips files and symlinks (we never follow symlinks out of base).
    Returns [] if base does not exist (target is configured but empty).
    """
    if not os.path.isdir(base):
        return []

    rows = []
    with os.scandir(base) as it:
        for entry in it:
            try:
                if entry.is_symlink():
                    continue
                if not entry.is_dir(follow_symlinks=False):
                    continue
                stat = entry.stat(follow_symlinks=False)
                rows.append((entry.name, entry.path, stat.st_mtime))
            except OSError as exc:
                logger.warning('inventory: stat failed for %s: %s', entry.path, exc)
                continue
    return rows


def _list_ssh(cfg, base):
    """Single SSH round trip — `find <base> -maxdepth 1 -mindepth 1 -type d -printf "%f\\t%T@\\n"`.

    Returns [(name, posix_join(base,name), mtime_epoch_float), ...].
    Returns [] if find exits 0 with no output (or base is missing).
    """
    for required in ('host', 'user', 'ssh_key'):
        if not cfg.get(required):
            raise InventoryError(
                f"SSH target missing required field {required!r}",
                http_status=500,
                code=e.INSTALL_CONFIG_ERROR,
            )

    base_q = shlex.quote(base)
    remote_cmd = (
        f"find {base_q} -maxdepth 1 -mindepth 1 -type d "
        f"-printf '%f\\t%T@\\n' 2>/dev/null || true"
    )
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
        completed = subprocess.run(
            ssh_cmd,
            timeout=settings.INSTALL_TIMEOUT_SECONDS,
            check=True,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        raise InventoryError(
            f'Inventory timed out after {settings.INSTALL_TIMEOUT_SECONDS}s',
            http_status=504,
            code=e.INVENTORY_FAILED,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b'').decode('utf-8', errors='replace')[:500].strip()
        raise InventoryError(
            f'ssh/find failed (exit {exc.returncode}): {stderr}',
            http_status=502,
            code=e.INVENTORY_FAILED,
        )

    rows = []
    for line in completed.stdout.decode('utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line or '\t' not in line:
            continue
        name, mtime_str = line.split('\t', 1)
        try:
            mtime = float(mtime_str)
        except ValueError:
            continue
        rows.append((name, base.rstrip('/') + '/' + name, mtime))
    return rows


def _mtime_iso(mtime_epoch):
    """Convert epoch timestamp to ISO 8601 string with Z suffix."""
    return datetime.fromtimestamp(mtime_epoch, tz=timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def list_installed_skills(target_name, user_name):
    """Return {target, base, catalog: [...], orphan: [...]}.

    Raises InventoryError(http_status=...) on any failure.
    """
    try:
        _validate_user_name(user_name)
    except InstallError as exc:
        raise InventoryError(str(exc), http_status=exc.http_status, code=exc.code)

    cfg = settings.INSTALL_TARGETS.get(target_name)
    if cfg is None:
        raise InventoryError(
            f"Unknown install target: {target_name!r}",
            http_status=400,
            code=e.INSTALL_TARGET_INVALID,
        )

    base_template = cfg.get('base')
    if not base_template:
        raise InventoryError(
            f"Target {target_name!r} missing 'base' config",
            http_status=500,
            code=e.INSTALL_CONFIG_ERROR,
        )
    base = base_template.format(user_name=user_name).rstrip('/\\')

    ttype = cfg.get('type')
    if ttype == 'local':
        rows = _list_local(base)
    elif ttype == 'ssh':
        rows = _list_ssh(cfg, base)
    else:
        raise InventoryError(
            f"Target {target_name!r} has unsupported type {ttype!r}",
            http_status=500,
            code=e.INSTALL_CONFIG_ERROR,
        )

    catalog_map = get_skills()
    catalog = []
    orphan = []
    for name, path, mtime in sorted(rows, key=lambda r: r[0].lower()):
        common = {'name': name, 'path': path, 'mtime': _mtime_iso(mtime)}
        hit = catalog_map.get(name)
        if hit is not None:
            catalog.append({
                **common,
                'icon': hit.get('icon'),
                'description': hit.get('description'),
                'fileCount': hit.get('fileCount'),
            })
        else:
            orphan.append(common)

    return {'target': target_name, 'base': base, 'catalog': catalog, 'orphan': orphan}
