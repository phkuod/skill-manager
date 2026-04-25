# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack note (README is stale)

`README.md` describes a Node/Express + React/Vite stack with `node manage.js` commands. That stack has been replaced. The running app is **Django 5.x** (4.x on Python 3.8/3.9) with server-rendered templates and vanilla JS. The `client/` directory contains only a leftover `node_modules/`; there is no frontend build step. Vendored Tailwind/highlight.js/marked live in `backend/skills/static/skills/vendor/`.

## Commands

All day-to-day operation goes through `./start.sh`, which picks a requirements file based on `python3 --version` (3.12+ → `requirements_py3.12.txt`, 3.10–3.11 → `requirements_py3.10_plus.txt`, else `requirements_py3.8_3.9.txt`) and expects a venv at `backend/venv`.

```bash
# First-time setup
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements-dev.txt   # dev (includes pytest)
# or backend/requirements.txt for prod-only

# Run
./start.sh            # dev — Django runserver on :3000
./start.sh prod       # prod — gunicorn, DEBUG=False

# Tests (from backend/ with venv active)
pytest                                       # all unit tests
pytest skills/tests/test_parser.py           # one file
pytest skills/tests/test_parser.py::test_x   # one test
pytest e2e/                                  # Playwright E2E (see caveat below)
```

PM2 is wired via `ecosystem.config.cjs` (`pm2 start ecosystem.config.cjs --env production`). It runs gunicorn out of `backend/`.

## Architecture

**No database.** `settings.py` uses `sqlite3 :memory:` purely to satisfy Django. The catalog lives in an in-process dict.

**Single Django app: `skills`.** Module responsibilities:

- `watcher.py` — owns the global `_skills` dict. `init_watcher()` runs a full `parse_all_skills()` on startup, then a `watchdog` observer re-parses with a 300ms debounce on any FS event under `SKILL_REPO_PATH`. `views.get_skills()` reads from this dict per request.
- `apps.py::SkillsConfig.ready()` — boots the watcher. Guards against Django autoreloader double-init by checking `RUN_MAIN`: initializes only when `RUN_MAIN == 'true'` (autoreload child) or unset (gunicorn/`--noreload`). **If you add startup work, preserve this guard or you'll get two watchers in dev.**
- `parser.py` — reads `SKILL.md` frontmatter (`python-frontmatter`). Handles **versioning**: any subdirectory matching `^(\d{8})-.+` that contains a `SKILL.md` is a version. When present, the newest by date becomes the active content; the top-level skill dir becomes the synthetic `"original"` version.
- `classifier.py` — `CATEGORY_MAP` is a **hardcoded** `skill_name → {category, icon}` table. Adding a new well-known skill requires an entry here; unknowns fall into `"Other" / 📦`.
- `file_reader.py` — recursive text-file walk for the detail view. Skips binaries (null-byte probe in first 8 KB); files >500 KB return `{content: None, truncated: True}`. Sort order: `SKILL.md` first, then alphabetical.
- `zipper.py` — builds the download ZIP in-memory (`io.BytesIO`); nothing is staged on disk.
- `views.py` — two HTML routes (`/`, `/skill/<name>`) and the `/api/*` JSON surface (see `skills/urls.py`). Server-side search sorts name-matches ahead of description-only matches.

**URL conventions.** `APPEND_SLASH = False` in `settings.py` — endpoints are `/api/skills`, not `/api/skills/`. Keep that in mind when adding routes or tests.

**Statics.** WhiteNoise serves collected assets; `./start.sh` runs `collectstatic --noinput` on every launch. Third-party CSS/JS are vendored under `backend/skills/static/skills/vendor/` — do not reintroduce a bundler.

## Tests

- Unit tests live in `backend/skills/tests/` (pytest-django, config in `backend/pytest.ini`). They read the real `skill_repo/` at the repo root; some (e.g. `test_views.py`) create and remove temporary version-subdirectory fixtures inside it.
- `backend/e2e/` uses Playwright against a subprocess-launched `runserver` on port 8799. **`conftest.py` hard-codes a Linux Chromium binary path** (`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`); E2E will not run on Windows/macOS without editing `CHROMIUM_EXEC`.

## Skill repository contract

`SKILL_REPO_PATH` (env, default `<repo>/skill_repo`) is the source of truth. Layout:

```
skill_repo/
  <skill-name>/
    SKILL.md                 # frontmatter: name, description, license
    ...
    20260331-some-variant/   # optional dated version dirs
      SKILL.md
```

Dropping or editing files here is the expected way to change the catalog — the watcher picks it up live.
