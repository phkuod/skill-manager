# Skill Market

A self-hosted web app for browsing, searching, and installing Claude Code /
Opencode CLI skills from a local skill repository. Designed for internal-network
deployment.

![Home](docs/screenshots/01-home.png)
![Skill Detail](docs/screenshots/02-skill-detail.png)

## Features

- Browse skills with real-time search and category filters
- Server-rendered first paint — skill cards are in the HTML before any JS runs
- Per-skill markdown documentation rendered server-side, syntax-highlighted client-side
- Install commands, one-click install (local copy or SSH/rsync), and ZIP download
- Dark / light theme (auto-detects system preference, persists across pages)
- Live reload — drop a new skill into `skill_repo/` and the catalog updates
  without a restart (filesystem watcher with 300 ms debounce)
- Keyboard shortcuts: `/` or `Ctrl+K` to focus search, `Esc` to clear / return
  to catalog, `D` to download the current skill ZIP

## Stack

- **Framework:** Django 4.x (Python 3.8–3.9) / Django 5.x (Python 3.10+), single app `skills`
- **Templates:** Django templates — server-side rendered, no client-side framework
- **Static assets:** vendored Tailwind CSS + highlight.js under `skills/static/skills/vendor/` (no bundler, no build step)
- **Storage:** none — the catalog is an in-memory dict refreshed by a `watchdog`
  observer over `SKILL_REPO_PATH`. SQLite `:memory:` satisfies Django's ORM requirement.
- **Process manager (prod):** PM2 + gunicorn

## Quick Start

```bash
git clone <repo-url>
cd skill-manager

# Create venv — start.sh picks the right requirements file for your Python version
python3 -m venv venv

# Run dev server (sources .env.development, collectstatic, then Django runserver on :3000)
./start.sh

# Run prod server (gunicorn, DEBUG=False)
./start.sh prod
```

Open <http://localhost:3000> (or the port set in `.env.development`).

To install dependencies manually, pick the file matching your Python version:

```bash
# Python 3.12+
pip install -r requirements_py3.12.txt

# Python 3.10–3.11
pip install -r requirements_py3.10_plus.txt

# Python 3.8–3.9
pip install -r requirements_py3.8_3.9.txt

# Add pytest + pytest-django for development
pip install pytest pytest-django
```

## Tests

From the repo root with the venv active:

```bash
pytest                                       # all unit tests
pytest skills/tests/test_parser.py           # one file
pytest skills/tests/test_parser.py::test_x   # one test
pytest e2e/                                  # Playwright E2E
```

E2E uses Playwright's bundled Chromium by default. Override with
`CHROMIUM_EXEC=/path/to/chrome` if you want a specific binary.

## Adding Skills

Drop a folder containing a `SKILL.md` into `skill_repo/`. The watcher picks it
up live — no restart needed.

```
skill_repo/
└── my-skill/
    ├── SKILL.md       # required — frontmatter: name, description, license
    │                  # optional: category, icon
    └── ...            # any other files
```

### Versioning

Subdirectories matching `yyyymmdd-<suffix>` that contain their own `SKILL.md`
are treated as versions. The newest by date becomes the active content; the
top-level directory is exposed as the synthetic `original` version.

```
skill_repo/
└── my-skill/
    ├── SKILL.md
    └── 20260331-rewrite/
        └── SKILL.md
```

## Environment Variables

| Variable            | Default                  | Purpose                                       |
|---------------------|--------------------------|-----------------------------------------------|
| `PORT`              | `3000`                   | HTTP port                                     |
| `SKILL_REPO_PATH`   | `<repo>/skill_repo`      | Source-of-truth catalog directory             |
| `LOG_FILE`          | `logs/skill-market.log`  | Rotating log file path                        |
| `LOG_LEVEL`         | `INFO`                   | `DEBUG` / `INFO` / `WARNING` / `ERROR`        |
| `LOG_MAX_BYTES`     | `10485760` (10 MB)       | Max log file size before rotation             |
| `LOG_BACKUP_COUNT`  | `5`                      | Number of rotated log files to keep           |
| `CHROMIUM_EXEC`     | (Playwright default)     | E2E Chromium binary override                  |

See `.env.example` for all supported variables.

## One-Click Install

The **Install** button on each skill detail page copies a skill directly into a user's skills directory. Configure one or more targets via environment variables:

```bash
# Local filesystem target
INSTALL_TARGET_F12_TYPE=local
INSTALL_TARGET_F12_BASE=/home/{user_name}/skills   # {user_name} filled from browser cookie

# Remote SSH target (uses rsync)
INSTALL_TARGET_F15_TYPE=ssh
INSTALL_TARGET_F15_BASE=/home/{user_name}/skills
INSTALL_TARGET_F15_HOST=devbox.internal
INSTALL_TARGET_F15_USER=deploy
INSTALL_TARGET_F15_SSH_KEY=/etc/ssh/deploy_key
```

`<NAME>` in `INSTALL_TARGET_<NAME>_*` is what appears in the UI. The `{user_name}` placeholder is substituted from the browser's `CURRENT_USER_NAME` cookie. Without the cookie, the install button shows a warning and is disabled.

## Production with PM2

```bash
pm2 start ecosystem.config.cjs --env production
pm2 save       # persist the process list
pm2 startup    # auto-start on system reboot

pm2 list
pm2 logs skill-market
pm2 restart skill-market
```

## Repository Layout

```
start.sh               # launcher — dev runserver or prod gunicorn
ecosystem.config.cjs   # PM2 spec (calls start.sh prod)
manage.py              # Django management entry point
Dockerfile             # for local prod simulation only (not used in real deploy)
.env.example           # all-keys reference template
requirements*.txt      # per-Python-version dependency files
skill_market/          # Django project — settings, root urls, wsgi
skills/                # the only Django app
  parser.py            # SKILL.md → skill dict (markdown pre-rendered to contentHtml)
  watcher.py           # filesystem observer + in-memory catalog
  classifier.py        # category / icon resolution
  installer.py         # one-click install (local copy or SSH rsync)
  file_reader.py       # detail-page recursive text walk
  zipper.py            # in-memory ZIP builder
  middleware.py        # CORS headers for /api/* only
  views.py             # HTML template views + JSON API
  templates/skills/    # base.html, home.html, skill_detail.html, 404.html
  static/skills/       # css/, js/, vendor/ (Tailwind, highlight.js)
  tests/               # pytest unit tests
e2e/                   # Playwright end-to-end tests
skill_repo/            # the catalog — add/edit skills here
logs/                  # rotating log files (gitignored)
docs/                  # specs, plans, architecture docs
```

See `CLAUDE.md` for architecture details and conventions.
