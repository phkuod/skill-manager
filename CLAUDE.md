# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack note (README is stale)

`README.md` describes a Node/Express + React/Vite stack with `node manage.js` commands. That stack has been replaced. The running app is **Django 5.x** with frontend served via Django templates from the `skills` app (`backend/skills/templates/skills/{base,home,skill_detail,404}.html`). Static assets live under `backend/skills/static/skills/...` and are picked up by Django's `APP_DIRS=True` static finder, then served by WhiteNoise. There is no frontend build step — vendored Tailwind and highlight.js live in `backend/skills/static/skills/vendor/`. SKILL.md markdown is pre-rendered to HTML in `parser.py` (the `contentHtml` field) and emitted in templates via `{{ skill.contentHtml|safe }}`.

## Commands

All day-to-day operation goes through `./backend/start.sh`, which picks a requirements file based on `python3 --version` (3.12+ → `requirements_py3.12.txt`, 3.10–3.11 → `requirements_py3.10_plus.txt`, else `requirements_py3.8_3.9.txt`) and expects a venv at `backend/venv`.

```bash
# First-time setup
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements-dev.txt   # dev (includes pytest)
# or backend/requirements.txt for prod-only

# Run
./backend/start.sh            # dev — Django runserver; PORT defaults to 3000, overridden by backend/.env.development (currently 8888)
./backend/start.sh prod       # prod — gunicorn, DEBUG=False (PORT from backend/.env.production)

# Tests (from backend/ with venv active)
pytest                                       # all unit tests
pytest skills/tests/test_parser.py           # one file
pytest skills/tests/test_parser.py::test_x   # one test
pytest e2e/                                  # Playwright E2E (see caveat below)
```

`backend/start.sh` sources `backend/.env.<mode>` if present, then runs `collectstatic` before launching. Production is also wired via PM2 (`backend/ecosystem.config.cjs`) and a Linux-only Dockerfile at the repo root (`docker build -t skill-market . && docker run -p 9419:9419 skill-market`). **Docker is only for simulating prod locally — the real production deployment uses the gunicorn/PM2 path, not the container.**

## Architecture

**No database.** `settings.py` uses `sqlite3 :memory:` purely to satisfy Django. The catalog lives in an in-process dict.

**Single Django app: `skills`.** Module responsibilities:

- `watcher.py` — owns the global `_skills` dict. `init_watcher()` runs a full `parse_all_skills()` on startup, then a `watchdog` observer re-parses with a 300ms debounce on any FS event under `SKILL_REPO_PATH`. `views.get_skills()` reads from this dict per request.
- `apps.py::SkillsConfig.ready()` — connects a `request_started` signal handler that lazy-inits the watcher on the first HTTP request (guarded by a module-level `_initialized` flag). This guarantees exactly one init regardless of launcher (runserver autoreload parent vs. child, `--noreload`, gunicorn worker) and skips management commands (`collectstatic`/`migrate`/`pytest`/`shell`). **Don't move init back into `ready()` directly — autoreload + `backend/start.sh`'s pre-launch `collectstatic` would each trigger their own `parse_all_skills()`.** Trade-off: first request pays the parse cost synchronously. Note: with `gunicorn --workers 2` each worker keeps its own `_skills` dict and watchdog observer; that's a known limitation of the in-process design.
- `parser.py` — reads `SKILL.md` frontmatter (`python-frontmatter`). Handles **versioning**: any subdirectory matching `^(\d{8})-.+` that contains a `SKILL.md` is a version. When present, the newest by date becomes the active content; the top-level skill dir becomes the synthetic `"original"` version.
- `classifier.py` — `CATEGORY_MAP` is a **hardcoded** `skill_name → {category, icon}` table. Adding a new well-known skill requires an entry here; unknowns fall into `"Other" / 📦`.
- `file_reader.py` — recursive text-file walk for the detail view. Skips binaries (null-byte probe in first 8 KB); files >500 KB return `{content: None, truncated: True}`. Sort order: `SKILL.md` first, then alphabetical.
- `zipper.py` — builds the download ZIP in-memory (`io.BytesIO`); nothing is staged on disk.
- `middleware.py::ApiCorsMiddleware` — adds permissive CORS (`Access-Control-Allow-Origin: *` by default) and short-circuits OPTIONS preflights, **only on `/api/*`**. Lock down for shared-host deploys via `CORS_ALLOWED_ORIGINS` (single origin only — browsers don't accept comma lists).
- `views.py` — HTML template views (`home` at `/`, `skill_detail` at `/skills/<name>/`, `skill_detail_version` at `/skills/<name>/v/<version>/`) that server-render the catalog and skill detail pages using data from the in-memory `_skills` dict. Plus the `/api/*` JSON surface (see `skills/urls.py`). Server-side search on `/api/skills` ranks name-matches > description-matches > content-matches.

**Env loading.** `settings.py:7` calls `load_dotenv(backend/.env)` *before* any `os.environ.get(...)`. `backend/.env` is gitignored, so its existence isn't obvious from a clean checkout — but if present, it silently overrides `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `INSTALL_TARGET_*`. Note this is **separate** from `backend/.env.development` / `backend/.env.production`, which are sourced by `backend/start.sh` *before* Django boots. If a deploy mysteriously gets blocked by CORS even though `backend/.env.development` looks right, check `backend/.env` first.

**URL conventions.** `APPEND_SLASH = False` in `settings.py` — endpoints are `/api/skills`, not `/api/skills/`. Keep that in mind when adding routes or tests. HTML routes are `/`, `/skills/<name>/`, `/skills/<name>/v/<version>/`. The `/index.html` and `/skill.html` shell routes were removed in the Django-templates migration.

**No CSRF middleware.** `MIDDLEWARE` (`settings.py:18-23`) deliberately omits `CsrfViewMiddleware`, so cross-origin `POST /api/install/run` works without a CSRF token. Auth on the install POST is by the `CURRENT_USER_NAME` cookie (the fetch sets `credentials: 'include'`). If you re-add CSRF, the cookie's SameSite policy becomes a split-deploy concern.

**Statics & frontend.** Static assets live in `backend/skills/static/skills/` and are picked up by `django.contrib.staticfiles` via `APP_DIRS=True`. WhiteNoise serves them in production after `collectstatic` populates `staticfiles/`. Templates live in `backend/skills/templates/skills/`. There is no `FRONTEND_DIR` environment variable, no `config.js`, and no separate static deploy — all paths resolve through `{% static %}`.

## Tests

- Unit tests live in `backend/skills/tests/` (pytest-django, config in `backend/pytest.ini`). They read the real `skill_repo/` at the repo root; some (e.g. `test_views.py`) create and remove temporary version-subdirectory fixtures inside it.
- `backend/e2e/` uses Playwright against a subprocess-launched `runserver` on port 8799. By default it uses Playwright's bundled Chromium; set `CHROMIUM_EXEC=/abs/path/to/chrome` to point at a system browser (useful for sandboxed/Linux CI environments where Playwright's download didn't run). The venv detection is OS-aware (`Scripts/python.exe` on Windows, `bin/python` elsewhere) and falls back to `sys.executable`.
- **Install modal UI smoke test**: `backend/skills/static/skills/dev/install-modal-ui-audit.js`. After ANY change to `skill_detail.html` modal markup or `skill.js` modal logic, open `/skills/<some-skill>/` in a browser, paste the file contents into DevTools console, and run. Must return `{passed: 64+, failed: 0}`. Catches the JIT-purged Tailwind trap (utility class missing from `backend/skills/static/skills/vendor/tailwind.min.css`), modal positioning regressions, theme-contrast failures, and click-flow regressions. Also embeds well in the test plan for any install-feature PR.

**JIT-purged Tailwind warning:** `frontend/vendor/tailwind.min.css` is a frozen JIT-purged build — only utilities that some element on the site uses at the time of the build are present. Adding a new element with a class that no other element uses (e.g. `.fixed`, `.inset-0`, `.max-w-md`, `.p-6` — all confirmed missing) silently breaks layout. When introducing a new utility, either verify it's already in the bundle or use an inline `style=""`. The audit script above tests this for the install modal specifically.

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
