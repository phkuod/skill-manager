# Installed Skills View + Uninstall — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/installed` page that lists what's installed on each target (F12 / F15 / F20) for the signed-in user and lets them safely uninstall a skill from a target via a type-to-confirm modal.

**Architecture:** Read-only scanning lives in a new `skills/inventory.py`; deletion logic extends `skills/installer.py` (so the existing `_resolve_target` / `_validate_user_name` / `InstallError` machinery stays the single source of truth). Two new legacy endpoints + two new v1 endpoints expose list + uninstall; a new Django template + JS file render the page; uninstall reuses the existing modal/toast UX patterns from the install flow.

**Tech Stack:** Django 5.x, vanilla JS (no build step), pytest-django, existing WhiteNoise static pipeline, vendored Tailwind (JIT-purged — do not introduce new utility classes), rsync over SSH for the existing install pipe (we keep using `ssh + rm` rather than rsync for uninstall).

**Design spec:** `C:\Users\phkuo\.claude\plans\i-need-to-design-lovely-steele.md`

---

## File map

```
NEW
 ├── skills/inventory.py
 ├── skills/templates/skills/installed.html
 ├── skills/static/skills/js/installed.js
 ├── skills/static/skills/dev/uninstall-modal-ui-audit.js
 ├── skills/tests/test_inventory.py
 ├── skills/tests/test_uninstall.py
 ├── skills/tests/test_views_installed.py
 └── skills/tests/test_views_v1_installed.py

EXTEND
 ├── skills/envelope.py                          (+5 error codes)
 ├── skills/installer.py                         (+_skill_name_re, _validate_skill_name,
 │                                                 uninstall_skill, _uninstall_local, _uninstall_ssh)
 ├── skills/views.py                             (+installed_page, +api_installed_list,
 │                                                 +api_installed_uninstall, +_do_uninstall helper)
 ├── skills/views_v1.py                          (+api_v1_installed_list, +api_v1_installed_uninstall)
 ├── skills/urls.py                              (+5 routes)
 ├── skills/templates/skills/base.html           (header nav link "Installed")
 └── skills/static/skills/css/app.css            (.installed-*, .uninstall-modal-* classes)
```

---

## Task 1: Add new error codes for inventory and uninstall

**Files:**
- Modify: `skills/envelope.py` (append constants near the existing INSTALL_* group)

- [ ] **Step 1: Add the error codes**

In `skills/envelope.py`, append below the `RSYNC_TIMEOUT = 'RSYNC_TIMEOUT'` line (before `RATE_LIMITED`):

```python
# Uninstall + inventory
UNINSTALL_FAILED = 'UNINSTALL_FAILED'
UNINSTALL_PATH_OUTSIDE_BASE = 'UNINSTALL_PATH_OUTSIDE_BASE'
UNINSTALL_TARGET_PATH_NOT_FOUND = 'UNINSTALL_TARGET_PATH_NOT_FOUND'
UNINSTALL_SKILL_NAME_INVALID = 'UNINSTALL_SKILL_NAME_INVALID'
INVENTORY_FAILED = 'INVENTORY_FAILED'
```

- [ ] **Step 2: Verify import surface**

Run: `python -c "from skills.envelope import UNINSTALL_FAILED, INVENTORY_FAILED, UNINSTALL_PATH_OUTSIDE_BASE, UNINSTALL_TARGET_PATH_NOT_FOUND, UNINSTALL_SKILL_NAME_INVALID; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add skills/envelope.py
git commit -m "feat: add error codes for inventory and uninstall"
```

---

## Task 2: Add skill-name validation helper to installer.py

**Files:**
- Modify: `skills/installer.py` (add `_skill_name_re` + `_validate_skill_name` next to existing `_user_name_re`)
- Test: `skills/tests/test_uninstall.py` (new file, partial)

- [ ] **Step 1: Write the failing test**

Create `skills/tests/test_uninstall.py`:

```python
import pytest

from skills.installer import (
    InstallError,
    _validate_skill_name,
)
from skills import envelope as e


def test_validate_skill_name_accepts_normal_names():
    _validate_skill_name('coding-guide')
    _validate_skill_name('webapp_testing')
    _validate_skill_name('skill.v2')
    _validate_skill_name('A-Bc_1.2')


@pytest.mark.parametrize('bad', [
    '',
    '..',
    '.',
    '...',
    '../etc',
    'a/b',
    'a\\b',
    'has space',
    'has;semi',
    'has$dollar',
    'has`backtick',
])
def test_validate_skill_name_rejects_traversal_and_specials(bad):
    with pytest.raises(InstallError) as ex:
        _validate_skill_name(bad)
    assert ex.value.http_status == 400
    assert ex.value.code == e.UNINSTALL_SKILL_NAME_INVALID
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/tests/test_uninstall.py -v`
Expected: `ImportError: cannot import name '_validate_skill_name'` (collection-time error).

- [ ] **Step 3: Implement**

In `skills/installer.py`, immediately below the existing `_validate_user_name` function:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest skills/tests/test_uninstall.py -v`
Expected: 14 passed (1 happy + 13 parametrized).

- [ ] **Step 5: Commit**

```bash
git add skills/installer.py skills/tests/test_uninstall.py
git commit -m "feat(installer): add _validate_skill_name with traversal guard"
```

---

## Task 3: Create skills/inventory.py with `InventoryError` and `_list_local`

**Files:**
- Create: `skills/inventory.py`
- Test: `skills/tests/test_inventory.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `skills/tests/test_inventory.py`:

```python
import os

import pytest

from skills.inventory import (
    InventoryError,
    _list_local,
)
from skills import envelope as e


def test_list_local_returns_directories(tmp_path):
    (tmp_path / 'alpha').mkdir()
    (tmp_path / 'beta').mkdir()
    (tmp_path / 'a_file.txt').write_text('hi')

    rows = _list_local(str(tmp_path))
    names = sorted(r[0] for r in rows)

    assert names == ['alpha', 'beta']
    for name, path, mtime in rows:
        assert path == os.path.join(str(tmp_path), name)
        assert isinstance(mtime, float)


def test_list_local_missing_base_returns_empty(tmp_path):
    nonexistent = str(tmp_path / 'does-not-exist')
    assert _list_local(nonexistent) == []


def test_list_local_skips_files_and_symlinks_to_dirs(tmp_path):
    (tmp_path / 'real').mkdir()
    (tmp_path / 'file.txt').write_text('x')
    try:
        os.symlink(str(tmp_path / 'real'), str(tmp_path / 'link'))
    except (OSError, NotImplementedError):
        pytest.skip('symlink unsupported on this platform')

    rows = _list_local(str(tmp_path))
    names = sorted(r[0] for r in rows)
    assert names == ['real']  # link is excluded — we don't follow out of base
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/tests/test_inventory.py -v`
Expected: `ModuleNotFoundError: No module named 'skills.inventory'`.

- [ ] **Step 3: Implement minimal `skills/inventory.py`**

Create `skills/inventory.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest skills/tests/test_inventory.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add skills/inventory.py skills/tests/test_inventory.py
git commit -m "feat(inventory): add InventoryError and _list_local scanner"
```

---

## Task 4: Add `_list_ssh` to inventory.py

**Files:**
- Modify: `skills/inventory.py` (append `_list_ssh`)
- Modify: `skills/tests/test_inventory.py` (append tests)

- [ ] **Step 1: Write the failing tests**

Append to `skills/tests/test_inventory.py`:

```python
import subprocess
from unittest.mock import patch, MagicMock

from skills.inventory import _list_ssh


def _ssh_cfg():
    return {
        'host': 'f15.intra.example',
        'user': 'svc-skillmarket',
        'ssh_key': '/etc/ssh/skillmarket_id_rsa',
    }


def test_list_ssh_parses_find_output():
    fake_stdout = b'coding-guide\t1715245391.0000000000\nlegacy-thing\t1722500000.5000000000\n'
    completed = MagicMock(returncode=0, stdout=fake_stdout, stderr=b'')

    with patch('skills.inventory.subprocess.run', return_value=completed) as run:
        rows = _list_ssh(_ssh_cfg(), '/AAA/coman/skills')

    args, kwargs = run.call_args
    cmd = args[0]
    assert cmd[0] == 'ssh'
    assert '-i' in cmd and '/etc/ssh/skillmarket_id_rsa' in cmd
    assert 'BatchMode=yes' in ' '.join(cmd)
    # remote command must use shlex-quoted base
    assert "'/AAA/coman/skills'" in cmd[-1] or '"/AAA/coman/skills"' in cmd[-1]

    names = sorted(r[0] for r in rows)
    assert names == ['coding-guide', 'legacy-thing']
    paths = {r[0]: r[1] for r in rows}
    assert paths['coding-guide'] == '/AAA/coman/skills/coding-guide'
    mtimes = {r[0]: r[2] for r in rows}
    assert mtimes['coding-guide'] == pytest.approx(1715245391.0)


def test_list_ssh_empty_output_returns_empty_list():
    completed = MagicMock(returncode=0, stdout=b'', stderr=b'')
    with patch('skills.inventory.subprocess.run', return_value=completed):
        assert _list_ssh(_ssh_cfg(), '/AAA/coman/skills') == []


def test_list_ssh_nonzero_exit_raises():
    err = subprocess.CalledProcessError(255, 'ssh', stderr=b'Permission denied')
    with patch('skills.inventory.subprocess.run', side_effect=err):
        with pytest.raises(InventoryError) as ex:
            _list_ssh(_ssh_cfg(), '/AAA/coman/skills')
    assert ex.value.http_status == 502


def test_list_ssh_timeout_raises():
    err = subprocess.TimeoutExpired(cmd='ssh', timeout=10)
    with patch('skills.inventory.subprocess.run', side_effect=err):
        with pytest.raises(InventoryError) as ex:
            _list_ssh(_ssh_cfg(), '/AAA/coman/skills')
    assert ex.value.http_status == 504


def test_list_ssh_missing_config_raises():
    with pytest.raises(InventoryError) as ex:
        _list_ssh({'host': '', 'user': '', 'ssh_key': ''}, '/AAA/coman/skills')
    assert ex.value.http_status == 500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/tests/test_inventory.py -v`
Expected: 5 errors at collection or runtime — `_list_ssh` does not exist.

- [ ] **Step 3: Implement `_list_ssh`**

Append to `skills/inventory.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest skills/tests/test_inventory.py -v`
Expected: 8 passed total (3 from Task 3 + 5 new).

- [ ] **Step 5: Commit**

```bash
git add skills/inventory.py skills/tests/test_inventory.py
git commit -m "feat(inventory): add _list_ssh with one-shot find over SSH"
```

---

## Task 5: Add `list_installed_skills` orchestrator with catalog enrichment

**Files:**
- Modify: `skills/inventory.py` (add `list_installed_skills`)
- Modify: `skills/tests/test_inventory.py` (append tests)

- [ ] **Step 1: Write the failing tests**

Append to `skills/tests/test_inventory.py`:

```python
from django.test import override_settings
from datetime import datetime, timezone

from skills.inventory import list_installed_skills
import skills.watcher as watcher_mod


def _fake_catalog():
    return {
        'coding-guide': {
            'name': 'coding-guide',
            'icon': '📘',
            'description': 'How to write clean code',
            'fileCount': 14,
        },
    }


def test_list_installed_skills_partitions_catalog_and_orphan(tmp_path):
    (tmp_path / 'coding-guide').mkdir()
    (tmp_path / 'legacy-thing').mkdir()
    cfg_base = str(tmp_path)

    with override_settings(
        INSTALL_TARGETS={'TEST': {'type': 'local', 'base': cfg_base}}
    ), patch.object(watcher_mod, '_skills', _fake_catalog()):
        result = list_installed_skills('TEST', 'coman')

    assert result['target'] == 'TEST'
    assert result['base'] == cfg_base

    catalog_names = [row['name'] for row in result['catalog']]
    orphan_names = [row['name'] for row in result['orphan']]
    assert catalog_names == ['coding-guide']
    assert orphan_names == ['legacy-thing']

    cg = result['catalog'][0]
    assert cg['icon'] == '📘'
    assert cg['description'] == 'How to write clean code'
    assert cg['fileCount'] == 14
    assert cg['path'].endswith('coding-guide')
    # mtime serialized as ISO-8601 with Z suffix
    assert cg['mtime'].endswith('Z')
    datetime.fromisoformat(cg['mtime'].replace('Z', '+00:00'))


def test_list_installed_skills_invalid_user_raises():
    with override_settings(INSTALL_TARGETS={'TEST': {'type': 'local', 'base': '/tmp/{user_name}/x'}}):
        with pytest.raises(InventoryError) as ex:
            list_installed_skills('TEST', '..')
    assert ex.value.http_status == 400


def test_list_installed_skills_unknown_target_raises():
    with override_settings(INSTALL_TARGETS={}):
        with pytest.raises(InventoryError) as ex:
            list_installed_skills('NOPE', 'coman')
    assert ex.value.http_status == 400


def test_list_installed_skills_missing_base_returns_empty_groups():
    cfg = {'type': 'local', 'base': '/this/does/not/exist/{user_name}'}
    with override_settings(INSTALL_TARGETS={'TEST': cfg}), \
         patch.object(watcher_mod, '_skills', {}):
        result = list_installed_skills('TEST', 'coman')
    assert result['catalog'] == []
    assert result['orphan'] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/tests/test_inventory.py -v -k list_installed_skills`
Expected: ImportError on `list_installed_skills`.

- [ ] **Step 3: Implement the orchestrator**

Append to `skills/inventory.py`:

```python
from datetime import datetime, timezone

from .installer import _validate_user_name, InstallError
from .watcher import get_skills


def _mtime_iso(mtime_epoch):
    return datetime.fromtimestamp(mtime_epoch, tz=timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def list_installed_skills(target_name, user_name):
    """Return {target, base, catalog: [...], orphan: [...]}.

    Raises InventoryError(http_status=...) on any failure.
    """
    # Validate user_name. _validate_user_name raises InstallError; remap.
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest skills/tests/test_inventory.py -v`
Expected: 12 passed total.

- [ ] **Step 5: Commit**

```bash
git add skills/inventory.py skills/tests/test_inventory.py
git commit -m "feat(inventory): add list_installed_skills with catalog/orphan partitioning"
```

---

## Task 6: Add `uninstall_skill` + `_uninstall_local` to installer.py

**Files:**
- Modify: `skills/installer.py` (append `uninstall_skill`, `_uninstall_local`)
- Modify: `skills/tests/test_uninstall.py` (append tests)

- [ ] **Step 1: Write the failing tests**

Append to `skills/tests/test_uninstall.py`:

```python
import os

from django.test import override_settings

from skills.installer import uninstall_skill


def test_uninstall_skill_local_removes_directory(tmp_path):
    base = tmp_path / 'coman' / 'skills'
    base.mkdir(parents=True)
    target = base / 'coding-guide'
    target.mkdir()
    (target / 'SKILL.md').write_text('---\nname: coding-guide\n---\n')

    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    with override_settings(INSTALL_TARGETS={'TEST': cfg}):
        result = uninstall_skill('TEST', 'coman', 'coding-guide')

    assert result == {'target': 'TEST', 'path': str(target)}
    assert not target.exists()
    # The base directory itself is preserved
    assert base.exists()


def test_uninstall_skill_local_missing_path_returns_404(tmp_path):
    base = tmp_path / 'coman' / 'skills'
    base.mkdir(parents=True)  # base exists but skill dir does not
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    with override_settings(INSTALL_TARGETS={'TEST': cfg}):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('TEST', 'coman', 'does-not-exist')
    assert ex.value.http_status == 404
    assert ex.value.code == e.UNINSTALL_TARGET_PATH_NOT_FOUND


def test_uninstall_skill_refuses_symlink(tmp_path):
    base = tmp_path / 'coman' / 'skills'
    base.mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'sentinel').write_text('keep-me')

    link = base / 'evil'
    try:
        os.symlink(str(outside), str(link))
    except (OSError, NotImplementedError):
        pytest.skip('symlink unsupported')

    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    with override_settings(INSTALL_TARGETS={'TEST': cfg}):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('TEST', 'coman', 'evil')
    assert ex.value.http_status == 409
    assert (outside / 'sentinel').exists()  # never followed


def test_uninstall_skill_invalid_user_rejected(tmp_path):
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    with override_settings(INSTALL_TARGETS={'TEST': cfg}):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('TEST', '..', 'coding-guide')
    assert ex.value.http_status == 400


def test_uninstall_skill_invalid_skill_name_rejected(tmp_path):
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    with override_settings(INSTALL_TARGETS={'TEST': cfg}):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('TEST', 'coman', '../etc')
    assert ex.value.http_status == 400


def test_uninstall_skill_unknown_target():
    with override_settings(INSTALL_TARGETS={}):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('NOPE', 'coman', 'coding-guide')
    assert ex.value.http_status == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/tests/test_uninstall.py -v -k uninstall_skill`
Expected: ImportError on `uninstall_skill`.

- [ ] **Step 3: Implement**

Append to `skills/installer.py`:

```python
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
    # If `dst` itself is a symlink, refuse before following it
    # (defense-in-depth against TOCTOU). os.path.islink is non-following.
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

    try:
        shutil.rmtree(dst)
    except OSError as exc:
        raise InstallError(
            f'rmtree failed: {exc}',
            http_status=500,
            code=e.UNINSTALL_FAILED,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest skills/tests/test_uninstall.py -v`
Expected: 20 passed total.

- [ ] **Step 5: Commit**

```bash
git add skills/installer.py skills/tests/test_uninstall.py
git commit -m "feat(installer): add uninstall_skill + _uninstall_local with traversal/symlink guards"
```

---

## Task 7: Add `_uninstall_ssh` to installer.py

**Files:**
- Modify: `skills/installer.py` (append `_uninstall_ssh`, ensure `shlex` is imported)
- Modify: `skills/tests/test_uninstall.py` (append SSH tests)

- [ ] **Step 1: Write the failing tests**

Append to `skills/tests/test_uninstall.py`:

```python
import subprocess
from unittest.mock import patch, MagicMock


def _ssh_target_cfg():
    return {
        'type': 'ssh',
        'base': '/AAA/{user_name}/skills',
        'host': 'f15.intra.example',
        'user': 'svc-skillmarket',
        'ssh_key': '/etc/ssh/skillmarket_id_rsa',
    }


def test_uninstall_skill_ssh_invokes_rm_with_quoted_path():
    completed = MagicMock(returncode=0, stdout=b'', stderr=b'')
    with override_settings(INSTALL_TARGETS={'F15': _ssh_target_cfg()}), \
         patch('skills.installer.subprocess.run', return_value=completed) as run:
        result = uninstall_skill('F15', 'coman', 'coding-guide')

    assert result == {
        'target': 'F15',
        'path': '/AAA/coman/skills/coding-guide',
    }
    args, _kwargs = run.call_args
    cmd = args[0]
    assert cmd[0] == 'ssh'
    assert 'BatchMode=yes' in ' '.join(cmd)
    # The remote command is the final positional argument; must contain
    # `rm -rf --` and the shlex-quoted absolute path.
    remote_cmd = cmd[-1]
    assert remote_cmd.startswith('rm -rf -- ')
    assert "'/AAA/coman/skills/coding-guide'" in remote_cmd


def test_uninstall_skill_ssh_nonzero_exit_raises_500():
    err = subprocess.CalledProcessError(1, 'ssh', stderr=b'rm: cannot remove')
    with override_settings(INSTALL_TARGETS={'F15': _ssh_target_cfg()}), \
         patch('skills.installer.subprocess.run', side_effect=err):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('F15', 'coman', 'coding-guide')
    assert ex.value.http_status == 500
    assert ex.value.code == e.UNINSTALL_FAILED


def test_uninstall_skill_ssh_timeout_raises_504():
    err = subprocess.TimeoutExpired(cmd='ssh', timeout=10)
    with override_settings(INSTALL_TARGETS={'F15': _ssh_target_cfg()}), \
         patch('skills.installer.subprocess.run', side_effect=err):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('F15', 'coman', 'coding-guide')
    assert ex.value.http_status == 504


def test_uninstall_skill_ssh_missing_host_raises_500():
    cfg = _ssh_target_cfg()
    cfg['host'] = ''
    with override_settings(INSTALL_TARGETS={'F15': cfg}):
        with pytest.raises(InstallError) as ex:
            uninstall_skill('F15', 'coman', 'coding-guide')
    assert ex.value.http_status == 500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/tests/test_uninstall.py -v -k ssh`
Expected: 4 errors — `_uninstall_ssh` not yet routed.

- [ ] **Step 3: Implement**

In `skills/installer.py`, add `import shlex` near the top of the imports section (alongside the existing `import shutil`, `import subprocess`).

Then append at the bottom of `skills/installer.py`:

```python
def _uninstall_ssh(cfg, dst, base):
    """SSH removal. Path-traversal guard via prefix check on POSIX strings."""
    # Both dst and base are POSIX-style (we forced forward slashes in
    # uninstall_skill before dispatch). Apply the same containment guard.
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest skills/tests/test_uninstall.py -v`
Expected: 24 passed total.

- [ ] **Step 5: Commit**

```bash
git add skills/installer.py skills/tests/test_uninstall.py
git commit -m "feat(installer): add _uninstall_ssh with rm -rf over SSH and path guard"
```

---

## Task 8: Legacy view handlers + URL routes

**Files:**
- Modify: `skills/views.py` (add `installed_page`, `api_installed_list`, `_do_uninstall`, `api_installed_uninstall`)
- Modify: `skills/urls.py` (add 3 routes — HTML page + 2 API)
- Test: `skills/tests/test_views_installed.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `skills/tests/test_views_installed.py`:

```python
import os
from unittest.mock import patch

import pytest
from django.test import Client, override_settings


@pytest.fixture
def client():
    return Client()


# ---------- HTML page ----------

def test_installed_page_renders(client):
    cfg = {'type': 'local', 'base': '/tmp/{user_name}/skills'}
    with override_settings(INSTALL_TARGETS={'F12': cfg}):
        res = client.get('/installed/')
    assert res.status_code == 200
    body = res.content.decode('utf-8')
    assert 'Installed skills' in body
    # Bootstrap JSON block must be present and contain at least F12
    assert 'installed-bootstrap' in body
    assert 'F12' in body


# ---------- API list ----------

def test_api_installed_list_missing_cookie_returns_400(client):
    with override_settings(INSTALL_TARGETS={'F12': {'type': 'local', 'base': '/tmp/{user_name}/skills'}}):
        res = client.get('/api/install/targets/F12/skills')
    assert res.status_code == 400
    assert 'cookie' in res.json()['error'].lower()


def test_api_installed_list_unknown_target_returns_400(client):
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={}):
        res = client.get('/api/install/targets/NOPE/skills')
    assert res.status_code == 400
    assert 'unknown' in res.json()['error'].lower()


def test_api_installed_list_happy_path_local(client, tmp_path):
    (tmp_path / 'coman' / 'skills' / 'coding-guide').mkdir(parents=True)
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={'F12': cfg}):
        res = client.get('/api/install/targets/F12/skills')
    assert res.status_code == 200
    body = res.json()
    assert body['target'] == 'F12'
    assert body['base'].endswith(os.path.join('coman', 'skills'))
    names = {row['name'] for row in body['catalog']} | {row['name'] for row in body['orphan']}
    assert 'coding-guide' in names


# ---------- API uninstall ----------

def test_api_installed_uninstall_missing_cookie(client):
    with override_settings(INSTALL_TARGETS={'F12': {'type': 'local', 'base': '/tmp/{user_name}/skills'}}):
        res = client.post('/api/install/targets/F12/skills/coding-guide/uninstall')
    assert res.status_code == 400


def test_api_installed_uninstall_happy_path_local(client, tmp_path):
    (tmp_path / 'coman' / 'skills' / 'coding-guide').mkdir(parents=True)
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={'F12': cfg}):
        res = client.post('/api/install/targets/F12/skills/coding-guide/uninstall')
    assert res.status_code == 200
    body = res.json()
    assert body['status'] == 'ok'
    assert body['target'] == 'F12'
    assert not (tmp_path / 'coman' / 'skills' / 'coding-guide').exists()


def test_api_installed_uninstall_path_not_found(client, tmp_path):
    (tmp_path / 'coman' / 'skills').mkdir(parents=True)
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={'F12': cfg}):
        res = client.post('/api/install/targets/F12/skills/nope/uninstall')
    assert res.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/tests/test_views_installed.py -v`
Expected: routing errors — endpoints not registered.

- [ ] **Step 3: Add URL routes**

In `skills/urls.py`, inside `urlpatterns`:

1. After the existing `skills/<str:name>/v/<str:version>/` line, add the HTML route:

```python
path('installed/', views.installed_page, name='installed_page'),
```

2. In the legacy API block (after `api_version_files`), add the 2 API routes:

```python
path('api/install/targets/<str:target_name>/skills',
     views.api_installed_list, name='api_installed_list'),
path('api/install/targets/<str:target_name>/skills/<str:name>/uninstall',
     views.api_installed_uninstall, name='api_installed_uninstall'),
```

- [ ] **Step 4: Implement view handlers**

In `skills/views.py`, update the installer import line:

Replace:
```python
from .installer import install_skill, InstallError
```
with:
```python
from .installer import install_skill, InstallError, uninstall_skill
from .inventory import list_installed_skills, InventoryError
```

Add at the top: `import json` is already imported.

Append at the bottom of `skills/views.py`:

```python
# ---------------------------------------------------------------------------
# Installed page + uninstall
# ---------------------------------------------------------------------------

def installed_page(request):
    """Render the installed-skills management page.

    Targets and the current user are passed to the template so the JS
    bootstrap can render section headers without an extra round trip.
    """
    user_name = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip()
    targets = [
        {'name': name, 'type': cfg.get('type', ''), 'base': cfg.get('base', ''), 'host': cfg.get('host', '')}
        for name, cfg in settings.INSTALL_TARGETS.items()
    ]
    return render(request, 'skills/installed.html', {
        'user_name': user_name,
        'targets': targets,
        'targets_json': json.dumps(targets),
    })


@require_GET
def api_installed_list(request, target_name):
    user_name = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip()
    if not user_name:
        return JsonResponse(
            {'error': 'Missing or invalid CURRENT_USER_NAME cookie'},
            status=400,
        )
    try:
        result = list_installed_skills(target_name, user_name)
    except InventoryError as exc:
        return JsonResponse({'error': str(exc)}, status=exc.http_status)
    return JsonResponse(result)


def _do_uninstall(request, target_name, name):
    user_name = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip()
    if not user_name:
        return JsonResponse(
            {'error': 'Missing or invalid CURRENT_USER_NAME cookie'},
            status=400,
        )
    try:
        result = uninstall_skill(target_name, user_name, name)
    except InstallError as exc:
        return JsonResponse({'error': str(exc)}, status=exc.http_status)
    return JsonResponse({'status': 'ok', **result})


@require_POST
def api_installed_uninstall(request, target_name, name):
    return _do_uninstall(request, target_name, name)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest skills/tests/test_views_installed.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add skills/urls.py skills/views.py skills/tests/test_views_installed.py
git commit -m "feat: legacy /installed page + /api/install/targets/<T>/skills endpoints"
```

---

## Task 9: v1 view handlers + URL routes

**Files:**
- Modify: `skills/views_v1.py` (add `api_v1_installed_list`, `api_v1_installed_uninstall`)
- Modify: `skills/urls.py` (add 2 v1 routes)
- Test: `skills/tests/test_views_v1_installed.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `skills/tests/test_views_v1_installed.py`:

```python
import pytest
from django.test import Client, override_settings


@pytest.fixture
def client():
    return Client()


def test_v1_installed_list_missing_cookie_envelope(client):
    with override_settings(INSTALL_TARGETS={'F12': {'type': 'local', 'base': '/tmp/{user_name}/skills'}}):
        res = client.get('/api/v1/install/targets/F12/skills')
    assert res.status_code == 400
    err = res.json()['error']
    assert 'code' in err and 'message' in err


def test_v1_installed_list_happy_path(client, tmp_path):
    (tmp_path / 'coman' / 'skills' / 'coding-guide').mkdir(parents=True)
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={'F12': cfg}):
        res = client.get('/api/v1/install/targets/F12/skills')
    assert res.status_code == 200
    body = res.json()
    assert 'data' in body
    assert body['data']['target'] == 'F12'


def test_v1_installed_uninstall_unknown_target_envelope(client):
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={}):
        res = client.post('/api/v1/install/targets/NOPE/skills/coding-guide/uninstall')
    assert res.status_code == 400
    body = res.json()
    assert body['error']['code'] == 'INSTALL_TARGET_INVALID'


def test_v1_installed_uninstall_happy_path(client, tmp_path):
    (tmp_path / 'coman' / 'skills' / 'coding-guide').mkdir(parents=True)
    cfg = {'type': 'local', 'base': str(tmp_path / '{user_name}' / 'skills')}
    client.cookies['CURRENT_USER_NAME'] = 'coman'
    with override_settings(INSTALL_TARGETS={'F12': cfg}):
        res = client.post('/api/v1/install/targets/F12/skills/coding-guide/uninstall')
    assert res.status_code == 200
    body = res.json()
    assert body['data']['status'] == 'ok'
    assert body['data']['target'] == 'F12'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/tests/test_views_v1_installed.py -v`
Expected: routing errors — v1 routes not registered.

- [ ] **Step 3: Add URL routes**

In `skills/urls.py`, in the v1 block (after `api_v1_version_files`):

```python
path('api/v1/install/targets/<str:target_name>/skills',
     views_v1.api_v1_installed_list, name='api_v1_installed_list'),
path('api/v1/install/targets/<str:target_name>/skills/<str:name>/uninstall',
     views_v1.api_v1_installed_uninstall, name='api_v1_installed_uninstall'),
```

- [ ] **Step 4: Implement v1 handlers**

In `skills/views_v1.py`, update the installer import line:

Replace:
```python
from .installer import install_skill, InstallError
```
with:
```python
from .installer import install_skill, InstallError, uninstall_skill
from .inventory import list_installed_skills, InventoryError
```

Append at the bottom of `skills/views_v1.py`:

```python
# ---------------------------------------------------------------------------
# Installed + uninstall (v1)
# ---------------------------------------------------------------------------

@require_GET
def api_v1_installed_list(request, target_name):
    user_name = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip()
    if not user_name:
        return e.err(
            e.INVALID_BODY,
            'Missing or invalid CURRENT_USER_NAME cookie',
            status=400,
        )
    try:
        result = list_installed_skills(target_name, user_name)
    except InventoryError as exc:
        return e.err(exc.code, str(exc), status=exc.http_status)
    return e.ok(result)


@require_POST
def api_v1_installed_uninstall(request, target_name, name):
    user_name = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip()
    if not user_name:
        return e.err(
            e.INVALID_BODY,
            'Missing or invalid CURRENT_USER_NAME cookie',
            status=400,
        )
    try:
        result = uninstall_skill(target_name, user_name, name)
    except InstallError as exc:
        return e.err(exc.code, str(exc), status=exc.http_status)
    return e.ok({'status': 'ok', **result})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest skills/tests/test_views_v1_installed.py -v`
Expected: 4 passed.

- [ ] **Step 6: Run full test suite to confirm no regressions**

Run: `pytest`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add skills/urls.py skills/views_v1.py skills/tests/test_views_v1_installed.py
git commit -m "feat(v1): /api/v1/install/targets/<T>/skills list + uninstall endpoints"
```

---

## Task 10: Add "Installed" nav link to base.html

**Files:**
- Modify: `skills/templates/skills/base.html`

- [ ] **Step 1: Locate the header block**

Read `skills/templates/skills/base.html`. Find the header `<a>` for "Back to catalog" and the theme-toggle `<button>`. The link will be inserted between them.

- [ ] **Step 2: Insert the nav link**

Inside `<header>`, immediately before the `<button id="theme-toggle"`, add:

```html
<a href="/installed/" id="nav-installed" class="text-sm font-medium px-3 py-2 rounded-lg border" style="color:var(--text-secondary);border-color:var(--border);text-decoration:none" title="View installed skills">
  Installed
</a>
```

Use only `style="..."` for colors — no new Tailwind utilities (vendored bundle is JIT-purged).

- [ ] **Step 3: Smoke-render the homepage**

Start the dev server: `./start.sh`
Open `http://127.0.0.1:8888/` and confirm an "Installed" pill appears in the header next to the theme toggle, in both light and dark themes.

- [ ] **Step 4: Commit**

```bash
git add skills/templates/skills/base.html
git commit -m "feat(ui): add 'Installed' nav link to base header"
```

---

## Task 11: Create `installed.html` template

**Files:**
- Create: `skills/templates/skills/installed.html`

- [ ] **Step 1: Write the template**

Create `skills/templates/skills/installed.html`:

```html
{% extends "skills/base.html" %}
{% load static %}

{% block title %}Installed Skills — Skill Market{% endblock %}

{% block content %}
<div class="max-w-5xl mx-auto px-6 py-8">
  <h1 class="text-2xl font-bold mb-1" style="color:var(--text-primary)">Installed skills</h1>
  <p class="text-sm mb-2" style="color:var(--text-secondary)">
    Manage skills installed under your account on each target.
  </p>
  <p class="text-sm mb-6" style="color:var(--text-secondary)">
    Signed in as: <strong>{{ user_name|default:"(not set)" }}</strong>
  </p>

  <div id="installed-sections">
    {% for t in targets %}
      <section class="installed-target" data-target="{{ t.name }}" data-type="{{ t.type }}">
        <button type="button" class="installed-target-header" aria-expanded="false">
          <span class="installed-target-caret">▸</span>
          <span class="installed-target-name">{{ t.name }}</span>
          <span class="installed-target-type">{{ t.type }}</span>
          {% if t.host %}<span class="installed-target-host">{{ t.host }}</span>{% endif %}
          <span class="installed-target-base">{{ t.base }}</span>
          <span class="installed-target-spacer" aria-hidden="true"></span>
          <span class="installed-target-refresh" hidden title="Refresh">↻</span>
        </button>
        <div class="installed-target-body" hidden></div>
      </section>
    {% endfor %}
  </div>
</div>

<!-- Uninstall confirmation modal -->
<div id="uninstall-modal" class="uninstall-modal" role="dialog" aria-modal="true" aria-labelledby="uninstall-modal-title" hidden>
  <div class="uninstall-modal-card">
    <button type="button" id="uninstall-modal-close" class="uninstall-modal-close" aria-label="Cancel">&times;</button>
    <h2 id="uninstall-modal-title" class="uninstall-modal-title">Remove skill?</h2>
    <dl class="uninstall-modal-details">
      <dt>Target</dt>     <dd id="uninstall-modal-target"></dd>
      <dt>Path</dt>       <dd id="uninstall-modal-path"></dd>
      <dt>Files</dt>      <dd id="uninstall-modal-files">–</dd>
      <dt>Last mod</dt>   <dd id="uninstall-modal-mtime">–</dd>
    </dl>
    <p class="uninstall-modal-warning">This action cannot be undone.</p>
    <label class="uninstall-modal-confirm-label" for="uninstall-modal-confirm-input">
      Type the skill name to confirm: <strong id="uninstall-modal-skill-name"></strong>
    </label>
    <input type="text" id="uninstall-modal-confirm-input" class="uninstall-modal-confirm-input" autocomplete="off" spellcheck="false">
    <div id="uninstall-modal-result" class="uninstall-modal-result" hidden></div>
    <div class="uninstall-modal-actions">
      <button type="button" id="uninstall-modal-cancel" class="btn-secondary">Cancel</button>
      <button type="button" id="uninstall-modal-confirm" class="btn-danger" disabled aria-disabled="true">Remove</button>
    </div>
  </div>
</div>

<script type="application/json" id="installed-bootstrap">
{{ targets_json|safe }}
</script>
<script src="{% static 'skills/js/common.js' %}"></script>
<script src="{% static 'skills/js/installed.js' %}"></script>
{% endblock %}
```

- [ ] **Step 2: Re-run the page-render test**

Run: `pytest skills/tests/test_views_installed.py::test_installed_page_renders -v`
Expected: PASS.

- [ ] **Step 3: Smoke-check in browser**

`./start.sh` → open `http://127.0.0.1:8888/installed/`. The three section headers should appear collapsed; the modal is hidden.

- [ ] **Step 4: Commit**

```bash
git add skills/templates/skills/installed.html
git commit -m "feat(ui): add /installed/ page template with target sections and uninstall modal"
```

---

## Task 12: `installed.js` — bootstrap, expand/collapse, first-render

**Files:**
- Create: `skills/static/skills/js/installed.js`

- [ ] **Step 1: Write the script**

Create `skills/static/skills/js/installed.js`:

```javascript
(function () {
  'use strict';

  // common.js exposes window.escapeHtml and window.toast
  const escapeHtml = window.escapeHtml || ((s) => String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]));
  const toast = window.toast || ((msg) => console.log('toast:', msg));

  const bootstrapEl = document.getElementById('installed-bootstrap');
  const TARGETS = bootstrapEl ? JSON.parse(bootstrapEl.textContent || '[]') : [];
  const cache = {}; // target -> {catalog, orphan, base}

  function fmtMtime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  }

  function renderRow(row, isOrphan) {
    const safeName = escapeHtml(row.name);
    const safePath = escapeHtml(row.path);
    const safeMtime = escapeHtml(fmtMtime(row.mtime));
    const icon = !isOrphan && row.icon ? escapeHtml(row.icon) : '📁';
    const description = !isOrphan && row.description ? escapeHtml(row.description) : '';
    const fileCount = !isOrphan && (row.fileCount || row.fileCount === 0) ? row.fileCount : '';
    const orphanClass = isOrphan ? ' installed-card-orphan' : '';
    const orphanBadge = isOrphan ? '<span class="installed-card-badge">Not in catalog</span>' : '';
    const filesLine = fileCount !== '' ? `${fileCount} files · ` : '';

    return (
      `<div class="installed-card${orphanClass}" data-name="${safeName}">
        <div class="installed-card-icon">${icon}</div>
        <div class="installed-card-body">
          <div class="installed-card-name">${safeName} ${orphanBadge}</div>
          ${description ? `<div class="installed-card-desc">${description}</div>` : ''}
          <div class="installed-card-meta">${filesLine}updated ${safeMtime}</div>
          <div class="installed-card-path">${safePath}</div>
        </div>
        <button type="button" class="installed-uninstall-btn"
                data-name="${safeName}"
                data-path="${safePath}"
                data-mtime="${safeMtime}"
                data-files="${fileCount}">Uninstall</button>
      </div>`
    );
  }

  function renderSection(body, data) {
    const catalogRows = data.catalog.map((r) => renderRow(r, false)).join('');
    const orphanRows = data.orphan.map((r) => renderRow(r, true)).join('');
    const html =
      `<div class="installed-group">
        <div class="installed-group-title">In catalog (${data.catalog.length})</div>
        ${data.catalog.length === 0 ? '<div class="installed-empty">No catalog skills installed on this target.</div>' : catalogRows}
      </div>` +
      (data.orphan.length > 0 ?
        `<div class="installed-group">
           <div class="installed-group-title">Not in catalog (${data.orphan.length})</div>
           ${orphanRows}
         </div>` : '');
    body.innerHTML = html;
    wireUninstallButtons(body);
  }

  function renderLoading(body) {
    body.innerHTML =
      '<div class="installed-skeleton"></div>'.repeat(3);
  }

  function renderError(body, message, retryFn) {
    body.innerHTML =
      `<div class="installed-error">
        <span>Couldn't reach target — ${escapeHtml(message)}</span>
        <button type="button" class="btn-secondary installed-retry-btn">Retry</button>
      </div>`;
    const btn = body.querySelector('.installed-retry-btn');
    if (btn) btn.addEventListener('click', retryFn);
  }

  async function fetchTarget(targetName) {
    const res = await fetch(`/api/install/targets/${encodeURIComponent(targetName)}/skills`, {
      credentials: 'include',
    });
    if (!res.ok) {
      let msg;
      try { msg = (await res.json()).error || `HTTP ${res.status}`; }
      catch (_e) { msg = `HTTP ${res.status}`; }
      throw new Error(msg);
    }
    return res.json();
  }

  function wireUninstallButtons(scope) {
    scope.querySelectorAll('.installed-uninstall-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const section = btn.closest('.installed-target');
        openUninstallModal({
          target: section.dataset.target,
          name: btn.dataset.name,
          path: btn.dataset.path,
          mtime: btn.dataset.mtime,
          files: btn.dataset.files,
          triggerEl: btn,
          sectionEl: section,
        });
      });
    });
  }

  async function loadSection(section, force) {
    const targetName = section.dataset.target;
    const body = section.querySelector('.installed-target-body');
    if (!force && cache[targetName]) {
      renderSection(body, cache[targetName]);
      return;
    }
    renderLoading(body);
    try {
      const data = await fetchTarget(targetName);
      cache[targetName] = data;
      renderSection(body, data);
    } catch (err) {
      renderError(body, err.message || String(err), () => loadSection(section, true));
    }
  }

  function wireSection(section) {
    const header = section.querySelector('.installed-target-header');
    const body = section.querySelector('.installed-target-body');
    const caret = section.querySelector('.installed-target-caret');
    const refresh = section.querySelector('.installed-target-refresh');

    header.addEventListener('click', (ev) => {
      if (refresh && refresh.contains(ev.target)) return;
      const expanded = header.getAttribute('aria-expanded') === 'true';
      const next = !expanded;
      header.setAttribute('aria-expanded', String(next));
      body.hidden = !next;
      caret.textContent = next ? '▾' : '▸';
      if (refresh) refresh.hidden = !next;
      if (next) loadSection(section, false);
    });

    if (refresh) {
      refresh.addEventListener('click', (ev) => {
        ev.stopPropagation();
        loadSection(section, true);
      });
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.installed-target').forEach(wireSection);
    // Mark nav link as current page for active styling
    const nav = document.getElementById('nav-installed');
    if (nav) nav.setAttribute('aria-current', 'page');
  });

  // Expose openUninstallModal placeholder; real impl appended in Task 13.
  window.openUninstallModal = window.openUninstallModal || function () {};
})();
```

- [ ] **Step 2: Smoke-check in browser**

`./start.sh` → open `http://127.0.0.1:8888/installed/`. Click a section header — it expands, shows a loading placeholder, then renders rows (or an empty state). Clicking again collapses. The "↻" refresh icon only shows when expanded and re-fetches when clicked.

- [ ] **Step 3: Commit**

```bash
git add skills/static/skills/js/installed.js
git commit -m "feat(ui): installed.js with lazy section loading and catalog/orphan rendering"
```

---

## Task 13: `installed.js` — uninstall modal + type-to-confirm + submit

**Files:**
- Modify: `skills/static/skills/js/installed.js` (append modal logic, replace the `openUninstallModal` placeholder)

- [ ] **Step 1: Replace the placeholder with the real implementation**

Inside `installed.js`, replace the placeholder line near the bottom of the IIFE:

```javascript
  window.openUninstallModal = window.openUninstallModal || function () {};
```

with the modal implementation below. Note: paste this BEFORE the closing `})();` of the IIFE so it has access to `cache` and `renderSection`.

```javascript
  const modal = document.getElementById('uninstall-modal');
  const modalCard = modal && modal.querySelector('.uninstall-modal-card');
  const modalClose = document.getElementById('uninstall-modal-close');
  const modalCancel = document.getElementById('uninstall-modal-cancel');
  const modalConfirm = document.getElementById('uninstall-modal-confirm');
  const modalInput = document.getElementById('uninstall-modal-confirm-input');
  const modalSkillName = document.getElementById('uninstall-modal-skill-name');
  const modalTarget = document.getElementById('uninstall-modal-target');
  const modalPath = document.getElementById('uninstall-modal-path');
  const modalFiles = document.getElementById('uninstall-modal-files');
  const modalMtime = document.getElementById('uninstall-modal-mtime');
  const modalTitle = document.getElementById('uninstall-modal-title');
  const modalResult = document.getElementById('uninstall-modal-result');

  let modalCtx = null;
  let lastFocus = null;

  function refreshConfirmState() {
    if (!modalCtx) return;
    const matches = modalInput.value.trim() === modalCtx.name;
    modalConfirm.disabled = !matches;
    modalConfirm.setAttribute('aria-disabled', String(!matches));
  }

  function setModalResult(message, isError) {
    if (!message) {
      modalResult.hidden = true;
      modalResult.textContent = '';
      modalResult.classList.remove('is-err', 'is-ok');
      return;
    }
    modalResult.textContent = message;
    modalResult.hidden = false;
    modalResult.classList.toggle('is-err', !!isError);
    modalResult.classList.toggle('is-ok', !isError);
  }

  function closeModal() {
    if (!modal) return;
    modal.classList.remove('is-open');
    modal.hidden = true;
    modalInput.value = '';
    setModalResult('', false);
    modalConfirm.disabled = true;
    modalConfirm.setAttribute('aria-disabled', 'true');
    modalCtx = null;
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
    lastFocus = null;
  }

  async function submitUninstall() {
    if (!modalCtx) return;
    modalConfirm.disabled = true;
    modalCancel.disabled = true;
    modalConfirm.textContent = 'Removing…';
    setModalResult('', false);

    const url = `/api/install/targets/${encodeURIComponent(modalCtx.target)}/skills/${encodeURIComponent(modalCtx.name)}/uninstall`;
    try {
      const res = await fetch(url, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      if (!res.ok) {
        let msg;
        try { msg = (await res.json()).error || `HTTP ${res.status}`; }
        catch (_e) { msg = `HTTP ${res.status}`; }
        throw new Error(msg);
      }
      // Remove the row from the section, decrement counts
      const section = modalCtx.sectionEl;
      const cached = cache[modalCtx.target];
      if (cached) {
        cached.catalog = cached.catalog.filter((r) => r.name !== modalCtx.name);
        cached.orphan = cached.orphan.filter((r) => r.name !== modalCtx.name);
        const body = section.querySelector('.installed-target-body');
        renderSection(body, cached);
      }
      toast(`Removed "${modalCtx.name}" from ${modalCtx.target}`, 'success');
      closeModal();
    } catch (err) {
      setModalResult(err.message || String(err), true);
    } finally {
      modalConfirm.textContent = 'Remove';
      modalCancel.disabled = false;
      refreshConfirmState();
    }
  }

  function openUninstallModal(ctx) {
    if (!modal) return;
    modalCtx = ctx;
    lastFocus = ctx.triggerEl || document.activeElement;
    modalTitle.textContent = `Remove "${ctx.name}" from ${ctx.target}?`;
    modalTarget.textContent = ctx.target;
    modalPath.textContent = ctx.path;
    modalFiles.textContent = ctx.files !== '' && ctx.files != null ? ctx.files : '–';
    modalMtime.textContent = ctx.mtime || '–';
    modalSkillName.textContent = ctx.name;
    modalInput.value = '';
    setModalResult('', false);
    modalConfirm.disabled = true;
    modalConfirm.setAttribute('aria-disabled', 'true');
    modal.hidden = false;
    requestAnimationFrame(() => modal.classList.add('is-open'));
    setTimeout(() => modalInput.focus(), 0);
  }

  window.openUninstallModal = openUninstallModal;

  if (modal) {
    modalInput.addEventListener('input', refreshConfirmState);
    modalConfirm.addEventListener('click', submitUninstall);
    modalCancel.addEventListener('click', closeModal);
    modalClose.addEventListener('click', closeModal);
    modal.addEventListener('click', (ev) => {
      if (ev.target === modal) closeModal();
    });
    document.addEventListener('keydown', (ev) => {
      if (modal.hidden) return;
      if (ev.key === 'Escape') {
        ev.preventDefault();
        closeModal();
      } else if (ev.key === 'Tab') {
        // simple focus trap: keep tab cycling inside the card
        const focusables = modalCard.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (ev.shiftKey && document.activeElement === first) {
          ev.preventDefault(); last.focus();
        } else if (!ev.shiftKey && document.activeElement === last) {
          ev.preventDefault(); first.focus();
        }
      }
    });
  }
```

- [ ] **Step 2: Smoke-check the modal flow**

Open `/installed/`, expand a target with at least one installed skill, click "Uninstall":
- Modal opens with target, path, files, mtime filled.
- Remove button disabled, Cancel enabled.
- Type wrong text → Remove stays disabled.
- Type the exact skill name → Remove enables.
- Press `Esc` → modal closes, focus returns to the originating Uninstall button.
- Click `×` → same behavior.
- Submit a successful uninstall → row disappears, success toast.
- Submit a forced-failure (e.g. delete the dir while modal is open) → red inline error, modal stays open, can retry after restoring.

- [ ] **Step 3: Commit**

```bash
git add skills/static/skills/js/installed.js
git commit -m "feat(ui): uninstall modal with type-to-confirm, focus trap, error preservation"
```

---

## Task 14: CSS for `.installed-*` and `.uninstall-modal-*`

**Files:**
- Modify: `skills/static/skills/css/app.css` (append at end)

- [ ] **Step 1: Append the styles**

Append to `skills/static/skills/css/app.css`. Use only plain CSS — no new Tailwind utilities (vendored bundle is JIT-purged).

```css
/* ---------- Installed page ---------- */
.installed-target {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--bg-secondary);
  margin-bottom: 12px;
  overflow: hidden;
}
.installed-target-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: transparent;
  border: 0;
  color: var(--text-primary);
  font: inherit;
  cursor: pointer;
  text-align: left;
}
.installed-target-header:hover {
  background: var(--bg-hover, rgba(127,127,127,0.08));
}
.installed-target-caret { width: 1ch; opacity: 0.7; }
.installed-target-name { font-weight: 600; }
.installed-target-type {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--text-secondary);
}
.installed-target-host {
  font-size: 0.75rem;
  color: var(--text-secondary);
}
.installed-target-base {
  font-size: 0.85rem;
  color: var(--text-secondary);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.installed-target-spacer { flex: 1; }
.installed-target-refresh {
  padding: 4px 8px;
  border-radius: 8px;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  cursor: pointer;
}
.installed-target-body {
  padding: 12px 16px 16px;
  border-top: 1px solid var(--border);
}
.installed-group { margin-top: 8px; }
.installed-group:first-child { margin-top: 0; }
.installed-group-title {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin: 4px 0 8px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.installed-card {
  display: grid;
  grid-template-columns: 48px 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-primary);
  margin-bottom: 8px;
}
.installed-card-orphan { opacity: 0.85; }
.installed-card-icon {
  width: 48px; height: 48px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.75rem;
  background: var(--bg-secondary);
  border-radius: 10px;
}
.installed-card-name { font-weight: 600; color: var(--text-primary); }
.installed-card-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 6px;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  margin-left: 8px;
}
.installed-card-desc { font-size: 0.9rem; color: var(--text-secondary); margin-top: 2px; }
.installed-card-meta { font-size: 0.8rem; color: var(--text-secondary); margin-top: 6px; }
.installed-card-path {
  font-size: 0.8rem;
  color: var(--text-secondary);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  margin-top: 2px;
  word-break: break-all;
}
.installed-uninstall-btn {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid #b42318;
  background: transparent;
  color: #b42318;
  font-weight: 600;
  cursor: pointer;
}
.installed-uninstall-btn:hover { background: rgba(180, 35, 24, 0.08); }
.installed-empty { color: var(--text-secondary); font-size: 0.9rem; padding: 8px; }
.installed-skeleton {
  height: 64px;
  border-radius: 10px;
  background: linear-gradient(90deg, rgba(127,127,127,0.08), rgba(127,127,127,0.16), rgba(127,127,127,0.08));
  background-size: 200% 100%;
  animation: installed-skel 1.4s ease-in-out infinite;
  margin-bottom: 8px;
}
@keyframes installed-skel {
  0% { background-position: 0% 0; }
  100% { background-position: -200% 0; }
}
.installed-error {
  display: flex; gap: 12px; align-items: center;
  padding: 12px; border-radius: 10px;
  background: rgba(180, 35, 24, 0.08);
  color: #b42318;
}

/* Nav-link active state */
#nav-installed[aria-current="page"] {
  background: var(--bg-hover, rgba(127,127,127,0.08));
  color: var(--text-primary);
}

/* ---------- Uninstall modal ---------- */
.uninstall-modal {
  position: fixed; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.45);
  opacity: 0;
  transition: opacity 120ms ease-out;
  z-index: 9999;
}
.uninstall-modal.is-open { opacity: 1; }
.uninstall-modal-card {
  width: min(520px, calc(100% - 32px));
  background: var(--bg-primary);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 24px;
  position: relative;
  box-shadow: 0 20px 50px rgba(0,0,0,0.25);
  transform: translateY(8px);
  transition: transform 120ms ease-out;
}
.uninstall-modal.is-open .uninstall-modal-card { transform: translateY(0); }
.uninstall-modal-close {
  position: absolute; top: 10px; right: 12px;
  background: transparent; border: 0; cursor: pointer;
  font-size: 1.4rem; color: var(--text-secondary); line-height: 1;
}
.uninstall-modal-title { font-size: 1.15rem; font-weight: 700; margin: 0 0 12px; }
.uninstall-modal-details {
  display: grid; grid-template-columns: 90px 1fr; gap: 4px 12px;
  font-size: 0.9rem;
  margin: 0 0 12px;
}
.uninstall-modal-details dt { color: var(--text-secondary); }
.uninstall-modal-details dd {
  margin: 0; word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.85rem;
}
.uninstall-modal-warning { color: #b42318; font-weight: 600; margin: 4px 0 12px; }
.uninstall-modal-confirm-label {
  display: block; font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 6px;
}
.uninstall-modal-confirm-input {
  width: 100%; box-sizing: border-box;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-family: inherit;
}
.uninstall-modal-result {
  margin-top: 12px; padding: 8px 12px; border-radius: 8px; font-size: 0.9rem;
}
.uninstall-modal-result.is-err { background: rgba(180,35,24,0.08); color: #b42318; }
.uninstall-modal-result.is-ok  { background: rgba(34,134,58,0.10); color: #22863a; }
.uninstall-modal-actions {
  display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px;
}
.btn-secondary {
  padding: 8px 14px; border-radius: 8px; border: 1px solid var(--border);
  background: transparent; color: var(--text-primary); cursor: pointer;
}
.btn-danger {
  padding: 8px 14px; border-radius: 8px; border: 1px solid #b42318;
  background: #b42318; color: #fff; font-weight: 600; cursor: pointer;
}
.btn-danger:disabled {
  opacity: 0.55; cursor: not-allowed;
}
```

- [ ] **Step 2: Re-collectstatic + smoke-check**

Restart `./start.sh` (so `collectstatic` runs) → open `/installed/`. Confirm in both light and dark themes:
- Section headers, cards, and modal use legible colors (no white-on-white).
- Modal is centered, the Remove button is red and disabled by default.
- Card "Uninstall" button is a red outlined button.
- Skeleton animation runs during loading.

- [ ] **Step 3: Commit**

```bash
git add skills/static/skills/css/app.css
git commit -m "style: add CSS for .installed-* and .uninstall-modal-* classes"
```

---

## Task 15: Create uninstall-modal UI audit + final verification

**Files:**
- Create: `skills/static/skills/dev/uninstall-modal-ui-audit.js`

- [ ] **Step 1: Write the audit script**

Create `skills/static/skills/dev/uninstall-modal-ui-audit.js`:

```javascript
/* Paste in DevTools console while viewing /installed/ with an expanded
   target that has at least one installed skill. Returns {passed,failed,results}. */
(async function () {
  const results = [];
  const T = (name, cond, detail) => results.push({ name, passed: !!cond, detail: detail || '' });

  // 1. Page has the bootstrap block
  T('bootstrap block exists', !!document.getElementById('installed-bootstrap'));

  // 2. At least one target section is rendered
  const sections = document.querySelectorAll('.installed-target');
  T('at least one target section', sections.length > 0);

  // 3. Expand the first section
  const first = sections[0];
  const header = first.querySelector('.installed-target-header');
  if (header.getAttribute('aria-expanded') !== 'true') header.click();
  await new Promise((r) => setTimeout(r, 1500));

  const body = first.querySelector('.installed-target-body');
  T('section body visible after click', !body.hidden);
  T('section body has rows or empty state',
    !!(body.querySelector('.installed-card') || body.querySelector('.installed-empty')));

  // 4. Click the first Uninstall button
  const btn = first.querySelector('.installed-uninstall-btn');
  if (btn) {
    btn.click();
    await new Promise((r) => setTimeout(r, 50));
    const modal = document.getElementById('uninstall-modal');
    T('modal opens on Uninstall click', !modal.hidden && modal.classList.contains('is-open'));

    const rect = modal.getBoundingClientRect();
    T('modal fills viewport', rect.width >= window.innerWidth * 0.99);

    const card = modal.querySelector('.uninstall-modal-card');
    const cardRect = card.getBoundingClientRect();
    T('modal card horizontally centered',
      Math.abs((cardRect.left + cardRect.right) / 2 - window.innerWidth / 2) < 20,
      `delta=${(cardRect.left + cardRect.right) / 2 - window.innerWidth / 2}`);

    const confirm = document.getElementById('uninstall-modal-confirm');
    T('Remove button initially disabled', confirm.disabled === true);
    T('Remove button has aria-disabled', confirm.getAttribute('aria-disabled') === 'true');

    const input = document.getElementById('uninstall-modal-confirm-input');
    input.value = 'WRONG-NAME';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    T('Remove stays disabled with wrong text', confirm.disabled === true);

    const skillName = btn.dataset.name;
    input.value = skillName;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    T('Remove enables when name matches', confirm.disabled === false);

    // close without submitting
    document.getElementById('uninstall-modal-close').click();
    await new Promise((r) => setTimeout(r, 200));
    T('modal closes on ×', modal.hidden === true);
  } else {
    T('Uninstall button available (skipped — no rows installed)', true, 'no installed skills to test');
  }

  const passed = results.filter((r) => r.passed).length;
  const failed = results.filter((r) => !r.passed).length;
  console.table(results);
  return { passed, failed, results };
})();
```

- [ ] **Step 2: Run the existing install-modal regression**

In a skill detail page (`/skills/<some-skill>/`), paste `skills/static/skills/dev/install-modal-ui-audit.js` into DevTools console. Expected: `{passed: 64+, failed: 0}`.

- [ ] **Step 3: Run the new uninstall-modal audit**

On `/installed/` with a section expanded that has at least one installed skill, paste `skills/static/skills/dev/uninstall-modal-ui-audit.js`. Expected: `{failed: 0}`.

- [ ] **Step 4: Backend smoke test**

```bash
curl -b "CURRENT_USER_NAME=coman" http://127.0.0.1:8888/api/install/targets/F12/skills
curl -b "CURRENT_USER_NAME=coman" http://127.0.0.1:8888/api/v1/install/targets/F12/skills
```

Expected: 200 for both, body shape matches the spec (legacy: flat; v1: `{data: {...}}`).

- [ ] **Step 5: Full pytest run**

Run: `pytest`
Expected: all green, no regressions in pre-existing tests.

- [ ] **Step 6: Manual E2E in both themes**

1. `./start.sh`
2. Visit `/installed/`. Header shows "Installed" pill.
3. Expand F12 → skills load.
4. Click Uninstall on a known throwaway skill → modal opens with correct details.
5. Type wrong, then correct, name → Remove enables.
6. Submit → row disappears, success toast.
7. Re-expand (or click ↻) → confirms the skill is gone.
8. Toggle theme → contrasts remain legible.

- [ ] **Step 7: Commit + push**

```bash
git add skills/static/skills/dev/uninstall-modal-ui-audit.js
git commit -m "test: add uninstall-modal UI audit script"
```

---

## Self-review notes

- **Spec coverage:** All 8 locked design decisions are implemented end-to-end (page route, by-target grouping, catalog enrichment, type-to-confirm modal, lazy section loading, header nav, orphan subsection, no version detection).
- **Safety guards in code:** regex on user + skill name (Tasks 2, 6, 7), `commonpath` containment guard local (Task 6), startswith containment guard ssh (Task 7), symlink refusal local (Task 6), `shlex.quote` ssh (Task 7), `BatchMode=yes` + `ConnectTimeout=10` (Tasks 4, 7), no follow-symlinks during local scan (Task 3).
- **Backward compat:** legacy `/api/install/targets` unchanged; both legacy and v1 surfaces added; no CSRF reintroduction; no Tailwind utility classes added (vendored bundle is JIT-purged).
- **Tests covered:** unit (inventory + uninstall), integration (legacy views + v1 views), manual (E2E + UI audits, both themes, regression on existing install-modal audit).
