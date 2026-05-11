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

from django.conf import settings

from . import envelope as e

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
