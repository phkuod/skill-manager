# Skill Market One-click Install — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-click "Install" action to the skill detail page that copies a skill directory to `/AAA/<user_name>/skills/<skill_name>/` on either the local F12 host (filesystem copy) or the remote F15 host (rsync over SSH).

**Architecture:** New backend module `skills/installer.py` owns both transport paths (local + ssh). Three new endpoints (`GET /api/install/targets`, `POST /api/skills/<name>/install`, `POST /api/skills/<name>/versions/<v>/install`). Targets are configured via prefixed env vars (`INSTALL_TARGET_<NAME>_*`) parsed once in `settings.py` into `INSTALL_TARGETS` dict. Frontend reads `CURRENT_USER_NAME` cookie, renders a confirmation modal with target previews, and calls the install API synchronously. Sync execution with 60-second timeout, no job queue.

**Tech Stack:** Django 5.x (Python 3.10+) / 4.x (3.8/3.9). Vanilla JS frontend (no build step). `shutil` for local copy, `subprocess.run(["rsync", ...])` for SSH path. `pytest-django` + `monkeypatch` for tests.

---

## File Structure

| File | Role |
|------|------|
| `backend/skills/installer.py` | NEW — `install_skill()` entry point, `InstallError`, local + ssh strategies, user_name validator |
| `backend/skill_market/settings.py` | MODIFY — parse `INSTALL_TARGET_*` env vars into `INSTALL_TARGETS`; add `INSTALL_TIMEOUT_SECONDS` |
| `backend/skills/middleware.py` | MODIFY — add `POST` to `Access-Control-Allow-Methods` |
| `backend/skills/views.py` | MODIFY — 3 new view fns + shared `_do_install()` helper |
| `backend/skills/urls.py` | MODIFY — wire 3 new routes |
| `backend/skills/tests/test_installer.py` | NEW — install_skill unit tests (local + mocked ssh + validation) |
| `backend/skills/tests/test_views_install.py` | NEW — endpoint tests (cookie, target validation, paths, response shape) |
| `backend/skills/tests/test_settings_install_targets.py` | NEW — env-var parsing |
| `frontend/skill.html` | MODIFY — install button under existing Install section + modal markup |
| `frontend/assets/skill.js` | MODIFY — `getCookie`, install targets fetch, modal open/close, install POST, result render |
| `.env.example` | MODIFY — document install-target keys |
| `.env.development.example` | MODIFY — dev-friendly defaults pointing to `/tmp` |
| `.env.production.example` | MODIFY — prod-shaped placeholder |

---

### Task 1: Parse `INSTALL_TARGET_*` env vars in settings

**Files:**
- Modify: `backend/skill_market/settings.py:43` (insert after the `SKILL_REPO_PATH` line)
- Test: `backend/skills/tests/test_settings_install_targets.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/skills/tests/test_settings_install_targets.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest skills/tests/test_settings_install_targets.py -v`
Expected: FAIL — `INSTALL_TARGETS` and `INSTALL_TIMEOUT_SECONDS` don't exist yet.

- [ ] **Step 3: Implement parsing in `settings.py`**

Add after `SKILL_REPO_PATH = ...` line (currently line 43):

```python
import re

INSTALL_TARGETS = {}
_install_target_re = re.compile(r'^INSTALL_TARGET_([A-Z0-9]+)_(.+)$')
for _k, _v in os.environ.items():
    _m = _install_target_re.match(_k)
    if _m:
        _name, _field = _m.group(1), _m.group(2).lower()
        INSTALL_TARGETS.setdefault(_name, {})[_field] = _v

INSTALL_TIMEOUT_SECONDS = int(os.environ.get('INSTALL_TIMEOUT_SECONDS', '60'))
```

Note: put `import re` at the top of the file with the other imports rather than inline.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest skills/tests/test_settings_install_targets.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/skill_market/settings.py backend/skills/tests/test_settings_install_targets.py
git commit -m "feat(install): parse INSTALL_TARGET_* env vars into INSTALL_TARGETS"
```

---

### Task 2: `installer.py` — module skeleton with `InstallError`

**Files:**
- Create: `backend/skills/installer.py`
- Test: `backend/skills/tests/test_installer.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/skills/tests/test_installer.py
import pytest

from skills.installer import InstallError


def test_install_error_carries_status_and_message():
    err = InstallError('bad target', http_status=400)
    assert str(err) == 'bad target'
    assert err.http_status == 400


def test_install_error_default_status_500():
    err = InstallError('boom')
    assert err.http_status == 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest skills/tests/test_installer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skills.installer'`.

- [ ] **Step 3: Create `installer.py` with `InstallError`**

```python
# backend/skills/installer.py
"""Skill install transport (local copy + ssh rsync).

Single entry point: install_skill(src_dir, target_name, user_name).
Raises InstallError(message, http_status) on any failure; views.py maps
the http_status straight onto the JSON response.
"""


class InstallError(Exception):
    def __init__(self, message, http_status=500):
        super().__init__(message)
        self.http_status = http_status
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest skills/tests/test_installer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/skills/installer.py backend/skills/tests/test_installer.py
git commit -m "feat(install): add installer module skeleton with InstallError"
```

---

### Task 3: `installer.py` — `_validate_user_name` + `_resolve_target`

**Files:**
- Modify: `backend/skills/installer.py`
- Modify: `backend/skills/tests/test_installer.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/skills/tests/test_installer.py`:

```python
from skills.installer import _validate_user_name, _resolve_target


def test_validate_user_name_accepts_alnum_dot_dash_underscore():
    _validate_user_name('jdoe')
    _validate_user_name('john.doe-2')
    _validate_user_name('A_B.C-1')


@pytest.mark.parametrize('bad', [
    '', '..', '../etc', 'a/b', 'a b', 'foo$', 'foo;rm', '\n', '\\\\path'])
def test_validate_user_name_rejects_traversal_and_specials(bad):
    with pytest.raises(InstallError) as exc:
        _validate_user_name(bad)
    assert exc.value.http_status == 400


def test_resolve_target_returns_config(settings):
    settings.INSTALL_TARGETS = {
        'F12': {'type': 'local', 'base': '/tmp/{user_name}/skills'},
    }
    cfg = _resolve_target('F12')
    assert cfg['type'] == 'local'


def test_resolve_target_unknown_raises_400(settings):
    settings.INSTALL_TARGETS = {}
    with pytest.raises(InstallError) as exc:
        _resolve_target('F99')
    assert exc.value.http_status == 400
    assert 'F99' in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest skills/tests/test_installer.py -v`
Expected: FAIL — `_validate_user_name` and `_resolve_target` not defined.

- [ ] **Step 3: Implement validators**

Append to `backend/skills/installer.py`:

```python
import re

from django.conf import settings

_user_name_re = re.compile(r'^[A-Za-z0-9_.-]+$')


def _validate_user_name(user_name):
    if not user_name or not _user_name_re.match(user_name):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest skills/tests/test_installer.py -v`
Expected: PASS (all tests added so far).

- [ ] **Step 5: Commit**

```bash
git add backend/skills/installer.py backend/skills/tests/test_installer.py
git commit -m "feat(install): add user_name + target validators"
```

---

### Task 4: `installer.py` — local-copy strategy

**Files:**
- Modify: `backend/skills/installer.py`
- Modify: `backend/skills/tests/test_installer.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/skills/tests/test_installer.py`:

```python
from skills.installer import install_skill


def _make_src(tmp_path, name='git-workflow'):
    src = tmp_path / 'repo' / name
    src.mkdir(parents=True)
    (src / 'SKILL.md').write_text('---\nname: git-workflow\n---\nbody', encoding='utf-8')
    (src / 'extra.txt').write_text('hello', encoding='utf-8')
    return str(src)


def test_install_local_copies_dir(tmp_path, settings):
    src = _make_src(tmp_path)
    base = tmp_path / 'dst' / '{user_name}' / 'skills'
    settings.INSTALL_TARGETS = {
        'LOCAL': {'type': 'local', 'base': str(base)},
    }

    result = install_skill(src, 'LOCAL', 'jdoe')

    expected = tmp_path / 'dst' / 'jdoe' / 'skills' / 'git-workflow'
    assert expected.is_dir()
    assert (expected / 'SKILL.md').read_text(encoding='utf-8') == '---\nname: git-workflow\n---\nbody'
    assert (expected / 'extra.txt').read_text(encoding='utf-8') == 'hello'
    assert result == {'target': 'LOCAL', 'path': str(expected)}


def test_install_local_overwrites_and_deletes_stale(tmp_path, settings):
    src = _make_src(tmp_path)
    base = tmp_path / 'dst' / '{user_name}' / 'skills'
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': str(base)}}

    # Pre-populate the target with a stale file that should be removed.
    stale_dir = tmp_path / 'dst' / 'jdoe' / 'skills' / 'git-workflow'
    stale_dir.mkdir(parents=True)
    (stale_dir / 'OLD.md').write_text('old', encoding='utf-8')

    install_skill(src, 'LOCAL', 'jdoe')

    assert not (stale_dir / 'OLD.md').exists()
    assert (stale_dir / 'SKILL.md').exists()


def test_install_local_rejects_bad_user_name(tmp_path, settings):
    src = _make_src(tmp_path)
    settings.INSTALL_TARGETS = {
        'LOCAL': {'type': 'local', 'base': str(tmp_path / '{user_name}')},
    }
    with pytest.raises(InstallError) as exc:
        install_skill(src, 'LOCAL', '../etc')
    assert exc.value.http_status == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest skills/tests/test_installer.py -v`
Expected: FAIL — `install_skill` not defined.

- [ ] **Step 3: Implement `install_skill` with local strategy**

Append to `backend/skills/installer.py`:

```python
import os
import shutil


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest skills/tests/test_installer.py -v`
Expected: PASS (all installer tests so far).

- [ ] **Step 5: Commit**

```bash
git add backend/skills/installer.py backend/skills/tests/test_installer.py
git commit -m "feat(install): local copy install strategy with overwrite semantics"
```

---

### Task 5: `installer.py` — SSH/rsync strategy

**Files:**
- Modify: `backend/skills/installer.py`
- Modify: `backend/skills/tests/test_installer.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/skills/tests/test_installer.py`:

```python
import subprocess
from unittest.mock import MagicMock


def test_install_ssh_invokes_rsync_with_expected_args(tmp_path, settings, monkeypatch):
    src = _make_src(tmp_path)
    settings.INSTALL_TARGETS = {
        'F15': {
            'type': 'ssh',
            'base': '/AAA/{user_name}/skills',
            'host': 'f15.example',
            'user': 'svc',
            'ssh_key': '/etc/ssh/k',
        },
    }
    settings.INSTALL_TIMEOUT_SECONDS = 60

    captured = {}

    def fake_run(cmd, **kwargs):
        captured['cmd'] = cmd
        captured['kwargs'] = kwargs
        return MagicMock(returncode=0, stderr=b'', stdout=b'')

    monkeypatch.setattr('skills.installer.subprocess.run', fake_run)

    result = install_skill(src, 'F15', 'jdoe')

    cmd = captured['cmd']
    assert cmd[0] == 'rsync'
    assert '-a' in cmd
    assert '--delete' in cmd
    assert '-e' in cmd
    e_idx = cmd.index('-e')
    ssh_str = cmd[e_idx + 1]
    assert 'ssh' in ssh_str
    assert '-i /etc/ssh/k' in ssh_str
    assert 'BatchMode=yes' in ssh_str

    # Source must end with trailing slash so contents (not the dir itself) go into dst.
    assert cmd[-2].rstrip('/').endswith('git-workflow')
    assert cmd[-2].endswith('/')
    # Dest is user@host:/path/skill_name/
    assert cmd[-1] == 'svc@f15.example:/AAA/jdoe/skills/git-workflow/'

    assert captured['kwargs']['timeout'] == 60
    assert captured['kwargs']['check'] is True
    assert captured['kwargs']['capture_output'] is True

    assert result == {'target': 'F15', 'path': '/AAA/jdoe/skills/git-workflow'}


def test_install_ssh_propagates_rsync_failure(tmp_path, settings, monkeypatch):
    src = _make_src(tmp_path)
    settings.INSTALL_TARGETS = {
        'F15': {
            'type': 'ssh', 'base': '/AAA/{user_name}/skills',
            'host': 'h', 'user': 'u', 'ssh_key': '/k',
        },
    }
    settings.INSTALL_TIMEOUT_SECONDS = 60

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=23, cmd=cmd, output=b'', stderr=b'rsync: connection refused')

    monkeypatch.setattr('skills.installer.subprocess.run', fake_run)

    with pytest.raises(InstallError) as exc:
        install_skill(src, 'F15', 'jdoe')
    assert exc.value.http_status == 502
    assert 'connection refused' in str(exc.value)


def test_install_ssh_timeout_raises_504(tmp_path, settings, monkeypatch):
    src = _make_src(tmp_path)
    settings.INSTALL_TARGETS = {
        'F15': {
            'type': 'ssh', 'base': '/AAA/{user_name}/skills',
            'host': 'h', 'user': 'u', 'ssh_key': '/k',
        },
    }
    settings.INSTALL_TIMEOUT_SECONDS = 5

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)

    monkeypatch.setattr('skills.installer.subprocess.run', fake_run)

    with pytest.raises(InstallError) as exc:
        install_skill(src, 'F15', 'jdoe')
    assert exc.value.http_status == 504
    assert 'timed out' in str(exc.value).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest skills/tests/test_installer.py -v -k ssh`
Expected: FAIL — ssh strategy not implemented (will hit the `unsupported type 'ssh'` branch).

- [ ] **Step 3: Implement SSH/rsync strategy**

Add at top of `backend/skills/installer.py` (with other imports):

```python
import subprocess
```

Replace the `if ttype == 'local':` branch in `install_skill` with:

```python
    if ttype == 'local':
        _install_local(src_dir, dst)
    elif ttype == 'ssh':
        _install_ssh(src_dir, dst, cfg)
    else:
        raise InstallError(
            f"Target {target_name!r} has unsupported type {ttype!r}",
            http_status=500,
        )
```

Add the SSH function at the bottom of the file:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest skills/tests/test_installer.py -v`
Expected: PASS (all installer tests).

- [ ] **Step 5: Commit**

```bash
git add backend/skills/installer.py backend/skills/tests/test_installer.py
git commit -m "feat(install): rsync-over-ssh install strategy"
```

---

### Task 6: Allow `POST` in CORS middleware

**Files:**
- Modify: `backend/skills/middleware.py:32`
- Test: `backend/skills/tests/test_middleware_cors.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/skills/tests/test_middleware_cors.py
import pytest
from django.test import Client


@pytest.mark.django_db
def test_options_allows_post_method():
    client = Client()
    resp = client.options('/api/skills/anything/install')
    assert resp.status_code == 204
    methods = resp.headers.get('Access-Control-Allow-Methods', '')
    assert 'POST' in methods
    assert 'GET' in methods
    assert 'OPTIONS' in methods
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest skills/tests/test_middleware_cors.py -v`
Expected: FAIL — `POST` not in `Access-Control-Allow-Methods`.

- [ ] **Step 3: Update middleware**

Modify `backend/skills/middleware.py` line 32:

```python
            response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest skills/tests/test_middleware_cors.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/skills/middleware.py backend/skills/tests/test_middleware_cors.py
git commit -m "feat(install): allow POST in /api CORS preflight"
```

---

### Task 7: `GET /api/install/targets` endpoint

**Files:**
- Modify: `backend/skills/views.py` (append at bottom)
- Modify: `backend/skills/urls.py` (add path)
- Test: `backend/skills/tests/test_views_install.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/skills/tests/test_views_install.py
import pytest
from django.test import Client


@pytest.mark.django_db
def test_install_targets_returns_name_and_base_only(settings):
    settings.INSTALL_TARGETS = {
        'F12': {'type': 'local', 'base': '/AAA/{user_name}/skills'},
        'F15': {
            'type': 'ssh',
            'base': '/AAA/{user_name}/skills',
            'host': 'secret.host',
            'user': 'svc',
            'ssh_key': '/etc/ssh/secret',
        },
    }
    resp = Client().get('/api/install/targets')
    assert resp.status_code == 200
    data = resp.json()
    targets = sorted(data['targets'], key=lambda t: t['name'])
    assert targets == [
        {'name': 'F12', 'base': '/AAA/{user_name}/skills'},
        {'name': 'F15', 'base': '/AAA/{user_name}/skills'},
    ]
    # Secrets must NOT leak.
    body = resp.content.decode('utf-8')
    assert 'secret.host' not in body
    assert 'svc' not in body
    assert 'secret' not in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest skills/tests/test_views_install.py -v`
Expected: FAIL — 404 (route does not exist).

- [ ] **Step 3: Add view + URL**

Append to `backend/skills/views.py`:

```python
@require_GET
def api_install_targets(request):
    targets = [
        {'name': name, 'base': cfg.get('base', '')}
        for name, cfg in settings.INSTALL_TARGETS.items()
    ]
    return JsonResponse({'targets': targets})
```

Add to `backend/skills/urls.py` `urlpatterns`:

```python
    path('api/install/targets', views.api_install_targets, name='api_install_targets'),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest skills/tests/test_views_install.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/skills/views.py backend/skills/urls.py backend/skills/tests/test_views_install.py
git commit -m "feat(install): GET /api/install/targets — names + base templates only"
```

---

### Task 8: `POST /api/skills/<name>/install` endpoint

**Files:**
- Modify: `backend/skills/views.py` (append)
- Modify: `backend/skills/urls.py`
- Modify: `backend/skills/tests/test_views_install.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/skills/tests/test_views_install.py`:

```python
import json


def _client_with_cookie(name='jdoe'):
    c = Client()
    c.cookies['CURRENT_USER_NAME'] = name
    return c


@pytest.mark.django_db
def test_install_unknown_skill_returns_404(settings):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': '/tmp/x'}}
    c = _client_with_cookie()
    resp = c.post(
        '/api/skills/no-such-skill/install',
        data=json.dumps({'target': 'LOCAL'}),
        content_type='application/json',
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_install_missing_cookie_returns_400(settings, tmp_path):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': str(tmp_path)}}
    c = Client()  # no cookie
    # Use any skill name; cookie check happens before skill lookup is irrelevant
    # but we still want a real skill to avoid 404 masking. Use a known skill.
    from skills.watcher import get_skills
    skills = list(get_skills().keys())
    if not skills:
        pytest.skip('skill_repo empty')
    resp = c.post(
        f'/api/skills/{skills[0]}/install',
        data=json.dumps({'target': 'LOCAL'}),
        content_type='application/json',
    )
    assert resp.status_code == 400
    assert 'CURRENT_USER_NAME' in resp.json()['error']


@pytest.mark.django_db
def test_install_missing_target_returns_400(settings):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': '/tmp/x'}}
    c = _client_with_cookie()
    from skills.watcher import get_skills
    skills = list(get_skills().keys())
    if not skills:
        pytest.skip('skill_repo empty')
    resp = c.post(
        f'/api/skills/{skills[0]}/install',
        data=json.dumps({}),  # no target
        content_type='application/json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_install_unknown_target_returns_400(settings):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': '/tmp/x'}}
    c = _client_with_cookie()
    from skills.watcher import get_skills
    skills = list(get_skills().keys())
    if not skills:
        pytest.skip('skill_repo empty')
    resp = c.post(
        f'/api/skills/{skills[0]}/install',
        data=json.dumps({'target': 'F99'}),
        content_type='application/json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_install_invalid_json_returns_400(settings):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': '/tmp/x'}}
    c = _client_with_cookie()
    from skills.watcher import get_skills
    skills = list(get_skills().keys())
    if not skills:
        pytest.skip('skill_repo empty')
    resp = c.post(
        f'/api/skills/{skills[0]}/install',
        data='not-json',
        content_type='application/json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_install_success_copies_skill(settings, tmp_path):
    base = tmp_path / 'dst' / '{user_name}' / 'skills'
    settings.INSTALL_TARGETS = {
        'LOCAL': {'type': 'local', 'base': str(base)},
    }
    c = _client_with_cookie('jdoe')
    from skills.watcher import get_skills
    skills = list(get_skills().keys())
    if not skills:
        pytest.skip('skill_repo empty')
    skill_name = skills[0]

    resp = c.post(
        f'/api/skills/{skill_name}/install',
        data=json.dumps({'target': 'LOCAL'}),
        content_type='application/json',
    )

    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body['status'] == 'ok'
    assert body['target'] == 'LOCAL'
    expected_path = tmp_path / 'dst' / 'jdoe' / 'skills' / skill_name
    assert body['path'] == str(expected_path)
    assert expected_path.is_dir()
    assert (expected_path / 'SKILL.md').is_file()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest skills/tests/test_views_install.py -v -k install`
Expected: FAIL — endpoint not yet routed.

- [ ] **Step 3: Add endpoint + helper to `views.py`**

Append to `backend/skills/views.py` (also extend imports at top):

```python
import json
from django.views.decorators.http import require_POST

from .installer import install_skill, InstallError
```

Then add:

```python
def _do_install(request, src_dir):
    """Shared body for both install endpoints. Returns JsonResponse."""
    user_name = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip()
    if not user_name:
        return JsonResponse(
            {'error': 'Missing or invalid CURRENT_USER_NAME cookie'},
            status=400,
        )

    try:
        payload = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    target = (payload.get('target') or '').strip() if isinstance(payload, dict) else ''
    if not target:
        return JsonResponse({'error': "Missing 'target' in body"}, status=400)

    try:
        result = install_skill(src_dir, target, user_name)
    except InstallError as e:
        return JsonResponse({'error': str(e)}, status=e.http_status)

    return JsonResponse({'status': 'ok', **result})


@require_POST
def api_skill_install(request, name):
    skill = get_skills().get(name)
    if skill is None:
        return JsonResponse({'error': f"Skill '{name}' not found"}, status=404)
    return _do_install(request, _skill_dir(name))
```

Add to `backend/skills/urls.py` `urlpatterns`:

```python
    path('api/skills/<str:name>/install', views.api_skill_install, name='api_skill_install'),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest skills/tests/test_views_install.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add backend/skills/views.py backend/skills/urls.py backend/skills/tests/test_views_install.py
git commit -m "feat(install): POST /api/skills/<name>/install"
```

---

### Task 9: `POST /api/skills/<name>/versions/<version>/install` endpoint

**Files:**
- Modify: `backend/skills/views.py` (append)
- Modify: `backend/skills/urls.py`
- Modify: `backend/skills/tests/test_views_install.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/skills/tests/test_views_install.py`:

```python
@pytest.mark.django_db
def test_version_install_unknown_version_returns_404(settings, tmp_path):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': str(tmp_path)}}
    c = _client_with_cookie()
    from skills.watcher import get_skills
    skills = list(get_skills().keys())
    if not skills:
        pytest.skip('skill_repo empty')
    resp = c.post(
        f'/api/skills/{skills[0]}/versions/99999999-nope/install',
        data=json.dumps({'target': 'LOCAL'}),
        content_type='application/json',
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_version_install_unknown_skill_returns_404(settings, tmp_path):
    settings.INSTALL_TARGETS = {'LOCAL': {'type': 'local', 'base': str(tmp_path)}}
    c = _client_with_cookie()
    resp = c.post(
        '/api/skills/no-such/versions/original/install',
        data=json.dumps({'target': 'LOCAL'}),
        content_type='application/json',
    )
    assert resp.status_code == 404


# Note: full success test for version install requires a versioned skill
# fixture; if skill_repo has one, add a smoke test, otherwise rely on the
# shared _do_install path covered by Task 8 tests.
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest skills/tests/test_views_install.py -v -k version_install`
Expected: FAIL — endpoint not routed.

- [ ] **Step 3: Add view + URL**

Append to `backend/skills/views.py`:

```python
@require_POST
def api_version_install(request, name, version):
    skill = get_skills().get(name)
    if skill is None:
        return JsonResponse({'error': f"Skill '{name}' not found"}, status=404)
    ver_dir = _version_dir(name, version)
    if ver_dir is None:
        return JsonResponse({'error': f"Version '{version}' not found"}, status=404)
    return _do_install(request, ver_dir)
```

Add to `backend/skills/urls.py` `urlpatterns`:

```python
    path('api/skills/<str:name>/versions/<str:version>/install',
         views.api_version_install, name='api_version_install'),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest skills/tests/test_views_install.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/skills/views.py backend/skills/urls.py backend/skills/tests/test_views_install.py
git commit -m "feat(install): POST /api/skills/<name>/versions/<v>/install"
```

---

### Task 10: Document install env vars in `.env.*.example`

**Files:**
- Modify: `.env.example`
- Modify: `.env.development.example`
- Modify: `.env.production.example`

- [ ] **Step 1: Append docs block to `.env.example`**

Append at the bottom of `.env.example`:

```
# ---------------------------------------------------------------------------
# Install targets (one-click install feature)
# ---------------------------------------------------------------------------
# Each install target is a group of INSTALL_TARGET_<NAME>_* keys. <NAME>
# appears verbatim in the UI ("Install to F12"). Allowed: A-Z, 0-9.
#
# Required fields:
#   _TYPE     'local' (filesystem on this host) or 'ssh' (rsync over SSH)
#   _BASE     Target dir; supports {user_name} placeholder.
#
# ssh-only fields:
#   _HOST     Remote host (DNS or IP)
#   _USER     SSH login user
#   _SSH_KEY  Absolute path to private key file (passwordless, BatchMode)
#
# Hard timeout for any single install (local copy or rsync). Default 60s.
# INSTALL_TIMEOUT_SECONDS=60

# Example layout (uncomment and edit per environment):
# INSTALL_TARGET_F12_TYPE=local
# INSTALL_TARGET_F12_BASE=/AAA/{user_name}/skills
#
# INSTALL_TARGET_F15_TYPE=ssh
# INSTALL_TARGET_F15_BASE=/AAA/{user_name}/skills
# INSTALL_TARGET_F15_HOST=f15.intra.example
# INSTALL_TARGET_F15_USER=svc-skillmarket
# INSTALL_TARGET_F15_SSH_KEY=/etc/ssh/skillmarket_id_rsa
```

- [ ] **Step 2: Append dev-friendly defaults to `.env.development.example`**

```
# Install targets — dev-only local fake to exercise the F12 path without
# touching real user dirs. F15 (ssh) needs real keys, leave it out in dev.
INSTALL_TARGET_F12_TYPE=local
INSTALL_TARGET_F12_BASE=/tmp/skills-dev/{user_name}/skills
```

- [ ] **Step 3: Append prod-shaped placeholder to `.env.production.example`**

```
# Install targets — prod values. Replace example host / user / key path.
INSTALL_TARGET_F12_TYPE=local
INSTALL_TARGET_F12_BASE=/AAA/{user_name}/skills

INSTALL_TARGET_F15_TYPE=ssh
INSTALL_TARGET_F15_BASE=/AAA/{user_name}/skills
INSTALL_TARGET_F15_HOST=f15.intra.example
INSTALL_TARGET_F15_USER=svc-skillmarket
INSTALL_TARGET_F15_SSH_KEY=/etc/ssh/skillmarket_id_rsa
```

- [ ] **Step 4: Verify Django still boots with these vars set**

Run from repo root:
```bash
cp .env.development.example backend/.env.tmp
ENV_FILE=backend/.env.tmp cd backend && python -c "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','skill_market.settings'); django.setup(); from django.conf import settings; print(settings.INSTALL_TARGETS)"
rm backend/.env.tmp
```
Expected: prints `{'F12': {'type': 'local', 'base': '/tmp/skills-dev/{user_name}/skills'}}`.

- [ ] **Step 5: Commit**

```bash
git add .env.example .env.development.example .env.production.example
git commit -m "docs(install): document INSTALL_TARGET_* env vars"
```

---

### Task 11: Frontend — Install button + modal markup in `skill.html`

**Files:**
- Modify: `frontend/skill.html`

- [ ] **Step 1: Add Install button to the right sidebar**

Locate the `Download ZIP` link (currently `frontend/skill.html:144-152`). Insert a new button **above** it:

```html
        <button id="install-button"
          class="flex items-center justify-center gap-2 w-full py-3 px-4 rounded-xl font-medium text-sm text-white"
          style="background-color:var(--accent)"
          title="Install to /AAA/<user>/skills/">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 4v12m0 0l-4-4m4 4l4-4M4 20h16"/>
          </svg>
          Install
        </button>
```

(Style mirrors the existing Download ZIP CTA so it slots into the same sidebar visually.)

- [ ] **Step 2: Add modal markup at end of `<body>` (before the script tags)**

Insert just before `<script src="vendor/marked.min.js"></script>` (currently `frontend/skill.html:159`):

```html
<div id="install-modal" class="hidden fixed inset-0 z-50 flex items-center justify-center"
     style="background-color:rgba(0,0,0,0.5)">
  <div class="rounded-xl p-6 w-full max-w-md mx-4"
       style="background-color:var(--bg-card);border:1px solid var(--border)">
    <h3 id="install-modal-title" class="text-lg font-semibold mb-4" style="color:var(--text-primary)"></h3>

    <div class="mb-3 text-sm">
      <span style="color:var(--text-secondary)">User:</span>
      <span id="install-modal-user" class="font-mono ml-1" style="color:var(--text-primary)"></span>
    </div>

    <div class="mb-4 text-sm">
      <p class="mb-1" style="color:var(--text-secondary)">Target preview:</p>
      <ul id="install-modal-targets" class="space-y-1"></ul>
    </div>

    <p id="install-modal-no-cookie" class="hidden mb-4 text-sm" style="color:var(--accent-error,#dc2626)">
      No CURRENT_USER_NAME cookie — cannot install.
    </p>

    <div id="install-modal-result" class="hidden mb-4 text-sm rounded-lg p-3"></div>

    <div id="install-modal-actions" class="flex gap-2 justify-end">
      <button id="install-modal-cancel" class="px-3 py-2 text-sm rounded-lg border"
              style="border-color:var(--border);color:var(--text-primary)">Cancel</button>
    </div>
  </div>
</div>
```

(The Install-to-X buttons are added dynamically in JS once targets are known. `install-modal-actions` will get them prepended; on result, Cancel becomes Close — see Task 13.)

- [ ] **Step 3: Verify markup is valid**

Open `frontend/skill.html` in a browser (just open the file directly) — no JS bound yet, so the modal stays hidden. Confirm no parse errors in DevTools console.

- [ ] **Step 4: Commit**

```bash
git add frontend/skill.html
git commit -m "feat(install): install button + modal markup on skill detail page"
```

---

### Task 12: Frontend — cookie reader + targets fetch in `skill.js`

**Files:**
- Modify: `frontend/assets/skill.js`

- [ ] **Step 1: Add helpers at the top of the IIFE in `skill.js`**

Insert after the `function showError(msg) { ... }` block (currently `skill.js:47-51`):

```javascript
  // ---------------------------------------------------------------------------
  // Install — helpers
  // ---------------------------------------------------------------------------

  function getCookie(name) {
    var prefix = name + '=';
    var parts = document.cookie.split(';');
    for (var i = 0; i < parts.length; i++) {
      var c = parts[i].trim();
      if (c.indexOf(prefix) === 0) return decodeURIComponent(c.slice(prefix.length));
    }
    return '';
  }

  function fetchInstallTargets() {
    return fetch(API_BASE + '/api/install/targets')
      .then(function (r) { return r.ok ? r.json() : { targets: [] }; })
      .then(function (data) { return data.targets || []; })
      .catch(function () { return []; });
  }

  function installUrl(name, version) {
    return apiBase(name, version) + '/install';
  }
```

- [ ] **Step 2: Verify in DevTools console**

Reload `skill.html` in a browser (with backend running), open DevTools console:

```js
// Manually evaluate (after the page loads), targets endpoint is unauth-public
fetch('/api/install/targets').then(r => r.json()).then(console.log)
document.cookie = 'CURRENT_USER_NAME=jdoe'
```

Expected: targets JSON returned with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/assets/skill.js
git commit -m "feat(install): cookie reader + install targets fetch helpers"
```

---

### Task 13: Frontend — modal open/close + install POST flow

**Files:**
- Modify: `frontend/assets/skill.js`

- [ ] **Step 1: Add modal logic to `skill.js`**

Insert after the helpers added in Task 12:

```javascript
  function openInstallModal() {
    var modal = document.getElementById('install-modal');
    var title = document.getElementById('install-modal-title');
    var userEl = document.getElementById('install-modal-user');
    var targetsEl = document.getElementById('install-modal-targets');
    var noCookieEl = document.getElementById('install-modal-no-cookie');
    var resultEl = document.getElementById('install-modal-result');
    var actionsEl = document.getElementById('install-modal-actions');
    var cancelBtn = document.getElementById('install-modal-cancel');

    var version = getVersion();
    var titleText = 'Install "' + skillName + '"' + (version ? ' (' + version + ')' : '');
    title.textContent = titleText;

    var user = getCookie('CURRENT_USER_NAME');
    userEl.textContent = user || '(none)';

    // Reset modal state
    resultEl.classList.add('hidden');
    resultEl.textContent = '';
    resultEl.removeAttribute('style');
    cancelBtn.textContent = 'Cancel';

    // Remove previously-injected install buttons (idempotent re-open)
    Array.prototype.forEach.call(
      actionsEl.querySelectorAll('.install-target-btn'),
      function (b) { b.remove(); }
    );

    targetsEl.innerHTML = '';
    noCookieEl.classList.toggle('hidden', !!user);

    fetchInstallTargets().then(function (targets) {
      if (!targets.length) {
        targetsEl.innerHTML = '<li style="color:var(--text-secondary)">'
          + '(no install targets configured — set INSTALL_TARGET_* env vars)</li>';
        return;
      }
      targetsEl.innerHTML = targets.map(function (t) {
        var path = user
          ? t.base.replace('{user_name}', user) + '/' + skillName
          : t.base.replace('{user_name}', '<user>') + '/' + skillName;
        return '<li class="font-mono text-xs" style="color:var(--text-primary)">'
          + escapeHtml(t.name) + ' &rarr; ' + escapeHtml(path) + '</li>';
      }).join('');

      targets.forEach(function (t) {
        var btn = document.createElement('button');
        btn.className = 'install-target-btn px-3 py-2 text-sm rounded-lg font-medium text-white';
        btn.style.backgroundColor = 'var(--accent)';
        btn.textContent = 'Install to ' + t.name;
        btn.disabled = !user;
        if (!user) btn.style.opacity = '0.5';
        btn.onclick = function () { performInstall(t.name, btn); };
        actionsEl.insertBefore(btn, cancelBtn);
      });
    });

    cancelBtn.onclick = closeInstallModal;
    modal.classList.remove('hidden');
  }

  function closeInstallModal() {
    document.getElementById('install-modal').classList.add('hidden');
  }

  function performInstall(targetName, clickedBtn) {
    var actionsEl = document.getElementById('install-modal-actions');
    var resultEl = document.getElementById('install-modal-result');
    var cancelBtn = document.getElementById('install-modal-cancel');
    var allBtns = actionsEl.querySelectorAll('button');
    Array.prototype.forEach.call(allBtns, function (b) { b.disabled = true; });
    clickedBtn.textContent = 'Installing…';

    fetch(installUrl(skillName, getVersion()), {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: targetName }),
    })
      .then(function (r) {
        return r.json().then(function (j) { return { ok: r.ok, body: j }; });
      })
      .then(function (out) {
        resultEl.classList.remove('hidden');
        if (out.ok) {
          resultEl.style.backgroundColor = 'rgba(34,197,94,0.15)';
          resultEl.style.color = 'rgb(22,101,52)';
          resultEl.textContent = '✓ Installed to ' + out.body.target + ': ' + out.body.path;
        } else {
          resultEl.style.backgroundColor = 'rgba(220,38,38,0.15)';
          resultEl.style.color = 'rgb(153,27,27)';
          resultEl.textContent = '✗ ' + (out.body.error || 'Install failed');
        }
      })
      .catch(function (err) {
        resultEl.classList.remove('hidden');
        resultEl.style.backgroundColor = 'rgba(220,38,38,0.15)';
        resultEl.style.color = 'rgb(153,27,27)';
        resultEl.textContent = '✗ Network error: ' + err.message;
      })
      .finally(function () {
        // Hide install buttons; turn Cancel into Close.
        Array.prototype.forEach.call(
          actionsEl.querySelectorAll('.install-target-btn'),
          function (b) { b.remove(); }
        );
        cancelBtn.textContent = 'Close';
        cancelBtn.disabled = false;
      });
  }
```

- [ ] **Step 2: Wire the Install button in `renderSkill`**

In `frontend/assets/skill.js`, inside `renderSkill()` after the line that wires the download link (`skill.js:85`), add:

```javascript
    var installBtn = document.getElementById('install-button');
    if (installBtn) installBtn.onclick = openInstallModal;
```

- [ ] **Step 3: Manually test the happy path**

1. Add this to `.env.development`:
   ```
   INSTALL_TARGET_F12_TYPE=local
   INSTALL_TARGET_F12_BASE=/tmp/skills-dev/{user_name}/skills
   ```
2. Run `./start.sh` — backend listens on port 8888 (per existing dev config).
3. In a browser open `http://localhost:8888/skill.html#<some-skill>`.
4. DevTools console: `document.cookie = 'CURRENT_USER_NAME=jdoe'`.
5. Click **Install** → modal shows User `jdoe` and `F12 → /tmp/skills-dev/jdoe/skills/<skill>`.
6. Click **Install to F12** → spinner → green ✓ message.
7. In a terminal: `ls /tmp/skills-dev/jdoe/skills/<skill>/SKILL.md` — must exist.

If any step fails, fix in this task before committing.

- [ ] **Step 4: Manually test cookie-missing path**

1. DevTools: `document.cookie = 'CURRENT_USER_NAME=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/'`
2. Reload, click Install → modal shows `User: (none)`, the red "No cookie" line, and the Install-to-F12 button is disabled.

- [ ] **Step 5: Commit**

```bash
git add frontend/assets/skill.js
git commit -m "feat(install): install modal flow with target preview and inline result"
```

---

### Task 14: End-to-end regression sweep

**Files:** none modified.

- [ ] **Step 1: Full backend test suite**

Run: `cd backend && pytest`
Expected: all tests pass, including pre-existing tests.

- [ ] **Step 2: Existing E2E suite**

Run: `cd backend && pytest e2e/`
Expected: pass (existing flows unchanged — install endpoints are additive).

- [ ] **Step 3: Manual cross-version test**

For a versioned skill in `skill_repo/`:
1. Visit `skill.html#<name>`, switch the version dropdown to a non-default version.
2. Click Install → confirm in DevTools network tab the request goes to `/api/skills/<name>/versions/<v>/install`.
3. Inspect installed dir contents to confirm it's the version-specific contents (not the active version's files).

- [ ] **Step 4: Manual SSH path smoke (optional, prod-only)**

This requires real SSH key + remote host. On a staging box only:
1. Set `INSTALL_TARGET_F15_*` to a real test host where the service account has SSH access.
2. From the UI, install to F15 and verify the target dir on F15.

If staging not available, skip — the unit tests in Task 5 cover the rsync invocation.

- [ ] **Step 5: Commit (only if any fixes were made; otherwise skip)**

If Steps 1-4 passed clean, no commit. Otherwise commit any small fixes individually.

---

## Self-Review Notes

Cross-checked the spec (`C:\Users\phkuo\.claude\plans\superpower-brainstorming-skill-market-async-reef.md`) against this plan:

- Q1 SSH key-based auth → Task 5 (`-i {ssh_key} -o BatchMode=yes`).
- Q2 overwrite semantics → Task 4 (`shutil.rmtree` then `copytree`) + Task 5 (`rsync --delete`).
- Q3 `INSTALL_TARGET_*` env parsing → Task 1.
- Q4 cookie missing handling → Task 8 (backend 400) + Task 13 (frontend disable + message).
- Q5 sync execution + 60s timeout → Task 1 (`INSTALL_TIMEOUT_SECONDS`) + Task 5 (`subprocess.run(timeout=...)`).
- Q6 versioned skills → Task 9.
- Q7 UI placement + inline modal result → Task 11 + Task 13.
- Targets endpoint hides secrets → Task 7 (test asserts no leak).
- Path traversal validation → Task 3.
- CORS POST → Task 6.

All spec sections covered. No `TBD`, no "implement appropriate error handling" placeholders. Function/symbol names consistent across tasks (`install_skill`, `_do_install`, `openInstallModal`, `performInstall`).
