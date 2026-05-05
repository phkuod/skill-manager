# Django Templates Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the skill-manager frontend from static HTML + JS hydration (`frontend/`) to Django templates served from the `skills` app, while preserving install-modal behavior and folding in two UI/UX fixes (loading flash + search affordances).

**Architecture:** Hybrid render — Django templates do the first paint server-side using data already in the in-memory `_skills` dict; existing JS keeps responsibility for the install modal, the file viewer (lazy-fetched via `/api/skills/<name>/files`), and live filter/sort/search after first user interaction. Skill detail moves from hash routing (`skill.html#<name>`) to path routing (`/skills/<name>/`, `/skills/<name>/v/<version>/`). Markdown is pre-rendered to HTML in the parser; highlight.js stays client-side for the file viewer.

**Tech Stack:** Django 5.x, vanilla JS (no build step), Python `markdown` library (new), existing `python-frontmatter` + `watchdog` + `whitenoise`, vendored Tailwind + highlight.js. Tests via `pytest-django` + Playwright.

**Spec reference:** `~/.claude/plans/mossy-wobbling-bonbon.md` (the approved design doc — copy to `docs/superpowers/specs/2026-05-05-django-templates-migration-design.md` as part of Task 1).

---

## File Structure

**New files:**
- `backend/skills/templates/skills/base.html` — `<html>`, `<head>`, theme-bootstrap script, header slot, footer, `{% block content %}`
- `backend/skills/templates/skills/home.html` — extends base; catalog page, server-rendered grid + search/category/sort controls
- `backend/skills/templates/skills/skill_detail.html` — extends base; metadata + server-rendered markdown + install modal markup
- `backend/skills/templates/skills/404.html` — minimal "not found" page
- `backend/skills/static/skills/css/app.css` — relocated from `frontend/assets/app.css`
- `backend/skills/static/skills/js/{common,home,skill}.js` — relocated from `frontend/assets/`
- `backend/skills/static/skills/vendor/{tailwind.min.css,github-dark.min.css,highlight.min.js}` — relocated from `frontend/vendor/`
- `backend/skills/static/skills/dev/install-modal-ui-audit.js` — relocated from `frontend/dev/`
- `docs/superpowers/specs/2026-05-05-django-templates-migration-design.md` — copy of the approved spec
- New test functions in existing test files (no new test files)

**Modified files:**
- `backend/skill_market/settings.py` — add `TEMPLATES`, drop `STATICFILES_DIRS=[FRONTEND_DIR]`, drop `FRONTEND_DIR`
- `backend/skills/urls.py` — replace shell + `re_path` static block with HTML-view routes
- `backend/skills/views.py` — replace `_read_shell`/`index_shell`/`skill_shell` with `home`/`skill_detail`/`skill_detail_version` views
- `backend/skills/parser.py` — add `contentHtml` field
- `backend/skills/static/skills/js/home.js` — drop on-load fetch; hydrate from JSON cache; result count + clear button; new card URLs
- `backend/skills/static/skills/js/skill.js` — drop hash routing; read `body.dataset.skillName`; drop `renderSkill()`; lazy file fetch
- `backend/skills/tests/test_views.py` — replace shell tests with HTML-view tests
- `backend/skills/tests/test_parser.py` — add `contentHtml` test
- `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/requirements_py3.10_plus.txt`, `backend/requirements_py3.12.txt`, `backend/requirements_py3.8_3.9.txt` — add `markdown`
- `CLAUDE.md` — update stack note, statics & frontend section, drop split-deploy + `FRONTEND_DIR` references
- `backend/e2e/` — update Playwright tests to use new URLs

**Deleted:**
- Entire `frontend/` directory (after migration verifies)

---

## Task 1: Cut feature branch and copy spec

**Files:**
- Create: `docs/superpowers/specs/2026-05-05-django-templates-migration-design.md`
- Branch: `feature/django-templates`

- [ ] **Step 1: Verify clean working tree on master**

Run: `git status`
Expected: only `M frontend/config.js` (existing modification — leave it; it'll be deleted later anyway)

- [ ] **Step 2: Cut and switch to the feature branch**

Run: `git checkout -b feature/django-templates`
Expected: `Switched to a new branch 'feature/django-templates'`

- [ ] **Step 3: Copy the approved spec into the repo**

Copy the entire content of `~/.claude/plans/mossy-wobbling-bonbon.md` to `docs/superpowers/specs/2026-05-05-django-templates-migration-design.md`. (The plans dir at `~/.claude/plans/` is transient; the in-repo location is canonical.)

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-05-05-django-templates-migration-design.md docs/superpowers/plans/2026-05-05-django-templates-migration.md
git commit -m "docs(specs): approved Django-templates migration design + plan"
```

---

## Task 2: Add markdown dependency

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements-dev.txt`
- Modify: `backend/requirements_py3.10_plus.txt`
- Modify: `backend/requirements_py3.12.txt`
- Modify: `backend/requirements_py3.8_3.9.txt`

- [ ] **Step 1: Add `markdown` to all five requirements files**

Append the line `markdown>=3.5,<4.0` to each of the five files listed above. (The base `requirements.txt` is what `requirements-dev.txt` references via `-r requirements.txt`, so most likely you only edit `requirements.txt` and the three `_py*` variants. Verify by reading the top of `requirements-dev.txt` first; if it uses `-r requirements.txt`, only edit the four. Otherwise edit all five.)

- [ ] **Step 2: Install in the venv**

Run (from repo root, with venv active): `backend/venv/Scripts/pip install -r backend/requirements-dev.txt` (Windows) or `backend/venv/bin/pip install -r backend/requirements-dev.txt` (POSIX).
Expected: `Successfully installed markdown-3.x.x`

- [ ] **Step 3: Smoke-test the import**

Run: `backend/venv/Scripts/python -c "import markdown; print(markdown.markdown('# hi'))"`
Expected output: `<h1>hi</h1>`

- [ ] **Step 4: Commit**

```bash
git add backend/requirements*.txt
git commit -m "build(deps): add markdown lib for server-side SKILL.md rendering"
```

---

## Task 3: Add `contentHtml` to the parser (TDD)

**Files:**
- Modify: `backend/skills/parser.py:68-91`
- Test: `backend/skills/tests/test_parser.py` (add new test functions)

- [ ] **Step 1: Write the failing test**

Add to `backend/skills/tests/test_parser.py` (after `test_parse_unversioned_null_version`, before the `parse_all_skills` section):

```python
def test_parse_content_html_renders_markdown(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'valid-skill'), 'valid-skill')
    assert '<h1>Valid Skill</h1>' in skill['contentHtml']
    assert '<h2>Usage</h2>' in skill['contentHtml']


def test_parse_content_html_supports_fenced_code(fixtures_dir):
    # Add a fenced code block to a temp skill and verify it renders.
    import tempfile, os
    tmp = tempfile.mkdtemp(prefix='skill-fenced-')
    skill_dir = os.path.join(tmp, 'fenced')
    os.makedirs(skill_dir)
    with open(os.path.join(skill_dir, 'SKILL.md'), 'w') as f:
        f.write(
            '---\nname: fenced\ndescription: x\nlicense: MIT\n---\n\n'
            '```python\nprint("hi")\n```\n'
        )
    skill = parse_skill(skill_dir, 'fenced')
    assert '<pre><code class="language-python">' in skill['contentHtml'] or \
           '<code class="language-python">' in skill['contentHtml']
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `pytest skills/tests/test_parser.py::test_parse_content_html_renders_markdown skills/tests/test_parser.py::test_parse_content_html_supports_fenced_code -v`
Expected: both FAIL with `KeyError: 'contentHtml'`

- [ ] **Step 3: Implement `contentHtml` in the parser**

In `backend/skills/parser.py`, add the import at the top (after existing imports, before the `from .classifier import classify` line):

```python
import markdown
```

Then in `parse_skill_from_dir` (around line 82-91), change the `return` block from:

```python
    return {
        'name': meta.get('name') or skill_name,
        'description': meta.get('description') or '',
        'license': meta.get('license') or 'Unknown',
        'category': classification['category'],
        'icon': classification['icon'],
        'fileCount': _count_files(dir_path),
        'lastUpdated': _last_modified(dir_path),
        'content': post.content,
    }
```

to:

```python
    # Pre-render markdown once per parse. SKILL.md is curated repo content,
    # not user input, so HTML sanitization is not needed.
    content_html = markdown.markdown(
        post.content,
        extensions=['fenced_code', 'tables'],
    )
    return {
        'name': meta.get('name') or skill_name,
        'description': meta.get('description') or '',
        'license': meta.get('license') or 'Unknown',
        'category': classification['category'],
        'icon': classification['icon'],
        'fileCount': _count_files(dir_path),
        'lastUpdated': _last_modified(dir_path),
        'content': post.content,
        'contentHtml': content_html,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest skills/tests/test_parser.py::test_parse_content_html_renders_markdown skills/tests/test_parser.py::test_parse_content_html_supports_fenced_code -v`
Expected: both PASS

- [ ] **Step 5: Run the full parser test suite to verify no regression**

Run: `pytest skills/tests/test_parser.py -v`
Expected: all tests PASS (the existing 22 tests + 2 new ones)

- [ ] **Step 6: Commit**

```bash
git add backend/skills/parser.py backend/skills/tests/test_parser.py
git commit -m "feat(parser): pre-render SKILL.md to contentHtml at parse time"
```

---

## Task 4: Add TEMPLATES setting

**Files:**
- Modify: `backend/skill_market/settings.py:13-16` (INSTALLED_APPS region) and add a TEMPLATES block

- [ ] **Step 1: Add the TEMPLATES setting**

In `backend/skill_market/settings.py`, after `MIDDLEWARE = [...]` and before `ROOT_URLCONF` (around line 24), insert:

```python
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.request',
        ],
    },
}]
```

- [ ] **Step 2: Verify Django boots cleanly**

Run (from `backend/`): `backend/venv/Scripts/python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add backend/skill_market/settings.py
git commit -m "feat(settings): configure Django templates engine (APP_DIRS=True)"
```

---

## Task 5: Move static assets into the app (`git mv`)

**Files:**
- Move: `frontend/assets/app.css` → `backend/skills/static/skills/css/app.css`
- Move: `frontend/assets/common.js` → `backend/skills/static/skills/js/common.js`
- Move: `frontend/assets/home.js` → `backend/skills/static/skills/js/home.js`
- Move: `frontend/assets/skill.js` → `backend/skills/static/skills/js/skill.js`
- Move: `frontend/vendor/tailwind.min.css` → `backend/skills/static/skills/vendor/tailwind.min.css`
- Move: `frontend/vendor/github-dark.min.css` → `backend/skills/static/skills/vendor/github-dark.min.css`
- Move: `frontend/vendor/highlight.min.js` → `backend/skills/static/skills/vendor/highlight.min.js`
- Move: `frontend/dev/install-modal-ui-audit.js` → `backend/skills/static/skills/dev/install-modal-ui-audit.js`
- Delete: `frontend/vendor/marked.min.js` (markdown is now server-rendered)

- [ ] **Step 1: Create the destination directories**

Run:
```bash
mkdir -p backend/skills/static/skills/css backend/skills/static/skills/js backend/skills/static/skills/vendor backend/skills/static/skills/dev
```

- [ ] **Step 2: `git mv` each file**

Run (one command per move; `git mv` preserves history):
```bash
git mv frontend/assets/app.css backend/skills/static/skills/css/app.css
git mv frontend/assets/common.js backend/skills/static/skills/js/common.js
git mv frontend/assets/home.js backend/skills/static/skills/js/home.js
git mv frontend/assets/skill.js backend/skills/static/skills/js/skill.js
git mv frontend/vendor/tailwind.min.css backend/skills/static/skills/vendor/tailwind.min.css
git mv frontend/vendor/github-dark.min.css backend/skills/static/skills/vendor/github-dark.min.css
git mv frontend/vendor/highlight.min.js backend/skills/static/skills/vendor/highlight.min.js
git mv frontend/dev/install-modal-ui-audit.js backend/skills/static/skills/dev/install-modal-ui-audit.js
git rm frontend/vendor/marked.min.js
```

- [ ] **Step 3: Verify static files resolve via `collectstatic --dry-run`**

Run (from `backend/`): `backend/venv/Scripts/python manage.py collectstatic --dry-run --noinput | head -40`
Expected: lists files like `Copying 'C:\...\backend\skills\static\skills\css\app.css'` — confirms `APP_DIRS`-style discovery picks them up. (At this point `STATICFILES_DIRS=[FRONTEND_DIR]` is still set, so files may also appear from `frontend/`'s remnants — that's fine; we clean up in Task 14.)

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(static): move assets from frontend/ into skills app static tree"
```

---

## Task 6: Build `base.html`

**Files:**
- Create: `backend/skills/templates/skills/base.html`

- [ ] **Step 1: Create the template**

Write the full content to `backend/skills/templates/skills/base.html`:

```django
{% load static %}<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Skill Market{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'skills/vendor/tailwind.min.css' %}">
  <link rel="stylesheet" href="{% static 'skills/vendor/github-dark.min.css' %}">
  <link rel="stylesheet" href="{% static 'skills/css/app.css' %}">
  <script>
    // Apply theme before first paint to avoid flash
    (function () {
      var stored = localStorage.getItem('theme');
      var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (stored === 'dark' || (!stored && prefersDark)) {
        document.documentElement.classList.add('dark');
      }
    })();
  </script>
</head>
<body class="min-h-screen"
      style="background-color:var(--bg-primary);color:var(--text-primary)"
      {% block body_attrs %}{% endblock %}>

{% block header %}{% endblock %}

{% block content %}{% endblock %}

<footer class="text-center py-4 text-sm border-t" style="color:var(--text-secondary);border-color:var(--border)">
  {% block footer %}<span id="footer-count">—</span> skills available{% endblock %}
</footer>

<script src="{% static 'skills/js/common.js' %}"></script>
{% block extra_scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add backend/skills/templates/skills/base.html
git commit -m "feat(templates): add base.html with theme bootstrap and static includes"
```

---

## Task 7: Create the `home` view + minimal `home.html` (TDD)

**Files:**
- Modify: `backend/skills/views.py` (add `home` view; leave `_read_shell` etc. alone for now)
- Modify: `backend/skills/urls.py` (add `path('', views.home, name='home')` ALONGSIDE existing routes)
- Create: `backend/skills/templates/skills/home.html` (minimal extends-base shell)
- Test: `backend/skills/tests/test_views.py` (add new test functions)

- [ ] **Step 1: Write failing tests**

Add to `backend/skills/tests/test_views.py`, near the bottom of the file:

```python
# ---------------------------------------------------------------------------
# HTML views (Django templates)
# ---------------------------------------------------------------------------

def test_home_renders_html(client, version_fixture):
    res = client.get('/')
    assert res.status_code == 200
    assert res['Content-Type'].startswith('text/html')


def test_home_contains_skill_name_in_initial_html(client, version_fixture):
    # Server-rendering contract: skill names must be present in the raw HTML
    # response, not injected by JS after page load.
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'pdf' in body or 'claude-api' in body  # both real skills in the repo
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `pytest skills/tests/test_views.py::test_home_renders_html skills/tests/test_views.py::test_home_contains_skill_name_in_initial_html -v`
Expected: FAIL — currently `/` returns the static `index.html` which contains *no* skill names (cards are JS-injected). The first test may pass (HTML is returned), but the second will fail.

- [ ] **Step 3: Add the new `home` view**

In `backend/skills/views.py`, add at the top of the imports section:

```python
from django.shortcuts import render
```

(`import json` is already present in the file; no need to add it again.)

Then add a new view function before the `# JSON API views` divider:

```python
@require_GET
def home(request):
    skills_dict = get_skills()
    skills = list(skills_dict.values())
    return render(request, 'skills/home.html', {
        'skills': skills,
        'categories': get_categories(skills_dict),
    })
```

- [ ] **Step 4: Wire the URL (replacing the static shell route)**

In `backend/skills/urls.py`, change the line `path('', views.index_shell, name='home'),` to `path('', views.home, name='home'),`. Leave the rest of the file unchanged for now (we'll prune in Task 14).

> **APPEND_SLASH note:** `settings.py` has `APPEND_SLASH = False`. The HTML routes added in Tasks 7, 10, and 13 use trailing slashes (`/skills/<name>/`). That means `/skills/pdf` (no slash) returns 404 — consistent with the existing API convention (`/api/skills/pdf` has no slash). All card `href` values in templates already use the trailing-slash form, so this only matters for externally typed URLs. Accepted asymmetry; no redirect is added.

- [ ] **Step 5: Create minimal `home.html`**

Write to `backend/skills/templates/skills/home.html`:

```django
{% extends "skills/base.html" %}

{% block content %}
<main class="px-6 py-8">
  <h1 style="color:var(--text-primary)">Skill Market</h1>
  <ul>
  {% for skill in skills %}
    <li><a href="/skills/{{ skill.name }}/">{{ skill.name }}</a> — {{ skill.description }}</li>
  {% endfor %}
  </ul>
</main>
{% endblock %}
```

(This is intentionally minimal — Task 8 expands it.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest skills/tests/test_views.py::test_home_renders_html skills/tests/test_views.py::test_home_contains_skill_name_in_initial_html -v`
Expected: both PASS.

- [ ] **Step 7: Run the full views test suite to verify no regression**

Run: `pytest skills/tests/test_views.py -v`
Expected: all tests pass (existing API tests still work; new HTML tests pass).

- [ ] **Step 8: Commit**

```bash
git add backend/skills/views.py backend/skills/urls.py backend/skills/templates/skills/home.html backend/skills/tests/test_views.py
git commit -m "feat(home): server-render catalog list at / via home.html"
```

---

## Task 8: Build full `home.html` with cards, search, categories, sort

**Files:**
- Modify: `backend/skills/templates/skills/home.html` (full replacement)

- [ ] **Step 1: Write the full home template**

Replace the entire content of `backend/skills/templates/skills/home.html` with:

```django
{% extends "skills/base.html" %}
{% load static %}

{% block title %}Skill Market{% endblock %}

{% block header %}
<header class="sticky top-0 z-50 border-b px-6 py-4 flex items-center gap-4" style="background-color:var(--bg-secondary);border-color:var(--border)">
  <div class="flex items-center gap-2 flex-shrink-0">
    <span class="text-2xl">🛍️</span>
    <span class="font-bold text-lg hidden sm:inline" style="color:var(--text-primary)">Skill Market</span>
  </div>
  <div class="flex-1 max-w-xl">
    <div class="relative">
      <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style="color:var(--text-secondary)" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
      </svg>
      <label for="search-input" class="sr-only">Search skills</label>
      <input id="search-input" type="text" placeholder="Search skills..."
        aria-label="Search skills"
        class="w-full pl-9 pr-16 py-2 rounded-lg border text-sm outline-none focus:ring-2"
        style="background-color:var(--bg-primary);color:var(--text-primary);border-color:var(--border)">
      <button id="search-clear" type="button" aria-label="Clear search"
        class="absolute top-1/2 -translate-y-1/2 hidden"
        style="right:2.25rem;padding:2px 6px;color:var(--text-secondary);background:transparent;border:0;cursor:pointer;font-size:1rem;line-height:1">×</button>
      <kbd id="search-shortcut-hint" title="Press / to focus search"
        class="absolute top-1/2 -translate-y-1/2 text-xs pointer-events-none"
        style="right:0.5rem;padding:2px 6px;border:1px solid var(--border);border-radius:4px;color:var(--text-secondary);background-color:var(--bg-secondary);font-family:inherit">/</kbd>
    </div>
  </div>
  <button id="theme-toggle" class="p-2 rounded-lg border flex-shrink-0" style="border-color:var(--border)" aria-label="Toggle theme">
    <svg id="icon-sun" class="w-5 h-5 hidden" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 5a7 7 0 100 14 7 7 0 000-14z"/>
    </svg>
    <svg id="icon-moon" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
    </svg>
  </button>
</header>
{% endblock %}

{% block content %}
<section class="px-6 py-10 text-center">
  <h1 class="text-3xl font-bold mb-2" style="color:var(--text-primary)">Internal Skill Market</h1>
  <p class="mb-6" style="color:var(--text-secondary)">Discover and install skills for Claude Code and Opencode CLI</p>
  <div class="flex justify-center gap-8 text-sm" style="color:var(--text-secondary)">
    <div><span id="stat-skills" class="font-bold text-lg" style="color:var(--accent)">{{ skills|length }}</span> Skills</div>
    <div><span id="stat-categories" class="font-bold text-lg" style="color:var(--accent)">{{ categories|length|add:"-1" }}</span> Categories</div>
    <div><span class="font-bold text-lg" style="color:var(--accent)">2</span> Platforms</div>
  </div>
</section>

<div class="px-6 mb-6 flex flex-wrap items-center gap-3">
  <div id="category-filters" class="flex flex-wrap gap-2">
    {% for cat in categories %}
      <button class="category-pill px-3 py-1 rounded-full text-sm border font-medium transition-colors{% if forloop.first %} active{% endif %}"
        data-category="{{ cat }}"
        style="border-color:var(--border);color:var(--text-secondary);background-color:var(--bg-secondary)">{{ cat }}</button>
    {% endfor %}
  </div>
  <div class="ml-auto flex items-center gap-2">
    <span id="result-count" class="text-sm" style="color:var(--text-secondary)">Showing {{ skills|length }} of {{ skills|length }}</span>
    <label for="sort-select" class="text-sm" style="color:var(--text-secondary)">Sort:</label>
    <select id="sort-select" class="text-sm rounded-lg border px-2 py-1"
      style="background-color:var(--bg-secondary);color:var(--text-primary);border-color:var(--border)">
      <option value="lastUpdated">Last Updated</option>
      <option value="name">Name</option>
    </select>
  </div>
</div>

<main class="px-6 pb-10">
  <div id="skill-grid" class="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
    {% for skill in skills %}
      <a href="/skills/{{ skill.name }}/"
         class="skill-card block rounded-xl border p-5 transition-all hover:shadow-lg"
         style="background-color:var(--bg-card);border-color:var(--border);text-decoration:none">
        <div class="flex items-start justify-between mb-3">
          <span class="text-3xl">{{ skill.icon }}</span>
          <span class="text-xs px-2 py-0.5 rounded-full category-badge" data-category="{{ skill.category }}">{{ skill.category }}</span>
        </div>
        <h3 class="font-semibold mb-1 truncate" style="color:var(--text-primary)">{{ skill.name }}</h3>
        <p class="text-sm mb-3 line-clamp-2" style="color:var(--text-secondary)">{{ skill.description }}</p>
        <div class="flex items-center justify-between text-xs" style="color:var(--text-secondary)">
          <span>{{ skill.fileCount }} file{{ skill.fileCount|pluralize }}</span>
          <span>{{ skill.lastUpdated|slice:":10" }}</span>
        </div>
      </a>
    {% endfor %}
  </div>
  <p id="no-results" class="hidden text-center py-12" style="color:var(--text-secondary)">No skills match your search.</p>
</main>

{{ skills|json_script:"skills-data" }}
{% endblock %}

{% block footer %}<span id="footer-count">{{ skills|length }}</span> skills available{% endblock %}

{% block extra_scripts %}
<script src="{% static 'skills/js/home.js' %}"></script>
{% endblock %}
```

- [ ] **Step 2: Smoke-test in the browser**

Run: `./backend/start.sh` (or `backend/venv/Scripts/python backend/manage.py runserver 8888`). Visit `http://localhost:8888/`.
Expected: catalog renders with all skills visible, category filter pills shown, sort dropdown shown. JS hasn't been updated yet so search/clear-button won't work — that's Task 9. The grid should be populated *before* JS runs (View Source confirms cards are in raw HTML).

- [ ] **Step 3: Commit**

```bash
git add backend/skills/templates/skills/home.html
git commit -m "feat(home): full server-rendered catalog template (cards, filters, controls)"
```

---

## Task 9: Update `home.js` — JSON cache, result count, clear button

**Files:**
- Modify: `backend/skills/static/skills/js/home.js` (full replacement)

- [ ] **Step 1: Replace the file**

Write the new content to `backend/skills/static/skills/js/home.js`:

```javascript
'use strict';

(function () {
  // Server-rendered first paint already populates the grid. JS takes over
  // on the first user interaction: hydrates `allSkills` from the inline
  // <script id="skills-data"> JSON block and re-renders via filter/sort/search.

  var allSkills = null;       // lazily filled from #skills-data on first interaction
  var categories = ['All'];
  var currentCategory = 'All';
  var currentSearch = '';
  var currentSort = 'lastUpdated';
  var debounceTimer = null;

  var skillGrid = document.getElementById('skill-grid');
  var noResults = document.getElementById('no-results');
  var footerCount = document.getElementById('footer-count');
  var resultCount = document.getElementById('result-count');
  var searchInput = document.getElementById('search-input');
  var searchClear = document.getElementById('search-clear');
  var sortSelect = document.getElementById('sort-select');
  var categoryFilters = document.getElementById('category-filters');

  function ensureSkillsLoaded() {
    if (allSkills !== null) return;
    var node = document.getElementById('skills-data');
    try {
      allSkills = JSON.parse(node.textContent);
    } catch (e) {
      allSkills = [];
    }
    // categories list isn't in the JSON block — pull from the rendered pills
    categories = Array.prototype.map.call(
      categoryFilters.querySelectorAll('.category-pill'),
      function (p) { return p.dataset.category; }
    );
  }

  function cardHtml(skill) {
    var updated = skill.lastUpdated || '';
    return (
      '<a href="/skills/' + encodeURIComponent(skill.name) + '/"' +
      ' class="skill-card block rounded-xl border p-5 transition-all hover:shadow-lg"' +
      ' style="background-color:var(--bg-card);border-color:var(--border);text-decoration:none">' +
        '<div class="flex items-start justify-between mb-3">' +
          '<span class="text-3xl">' + escapeHtml(skill.icon) + '</span>' +
          '<span class="text-xs px-2 py-0.5 rounded-full category-badge" data-category="' + escapeHtml(skill.category) + '">' +
            escapeHtml(skill.category) +
          '</span>' +
        '</div>' +
        '<h3 class="font-semibold mb-1 truncate" style="color:var(--text-primary)">' + escapeHtml(skill.name) + '</h3>' +
        '<p class="text-sm mb-3 line-clamp-2" style="color:var(--text-secondary)">' + escapeHtml(skill.description) + '</p>' +
        '<div class="flex items-center justify-between text-xs" style="color:var(--text-secondary)">' +
          '<span>' + skill.fileCount + ' file' + (skill.fileCount === 1 ? '' : 's') + '</span>' +
          '<span>' + escapeHtml(relativeTime(updated) || updated.slice(0, 10)) + '</span>' +
        '</div>' +
      '</a>'
    );
  }

  function matchRank(skill, q) {
    if ((skill.name || '').toLowerCase().indexOf(q) !== -1) return 0;
    if ((skill.description || '').toLowerCase().indexOf(q) !== -1) return 1;
    if ((skill.content || '').toLowerCase().indexOf(q) !== -1) return 2;
    return -1;
  }

  function render() {
    ensureSkillsLoaded();
    var q = currentSearch.toLowerCase();
    var visible = allSkills.filter(function (s) {
      var matchCat = currentCategory === 'All' || s.category === currentCategory;
      if (!matchCat) return false;
      if (!q) return true;
      return matchRank(s, q) !== -1;
    });
    visible.sort(function (a, b) {
      if (currentSort === 'name') return (a.name || '').localeCompare(b.name || '');
      return (b.lastUpdated || '').localeCompare(a.lastUpdated || '');
    });
    if (q) visible.sort(function (a, b) { return matchRank(a, q) - matchRank(b, q); });

    skillGrid.innerHTML = visible.map(cardHtml).join('');
    noResults.classList.toggle('hidden', visible.length > 0);
    if (footerCount) footerCount.textContent = visible.length;
    if (resultCount) resultCount.textContent = 'Showing ' + visible.length + ' of ' + allSkills.length;
    if (searchClear) searchClear.classList.toggle('hidden', !currentSearch);
  }

  // Wire category pills (already server-rendered)
  Array.prototype.forEach.call(categoryFilters.querySelectorAll('.category-pill'), function (pill) {
    pill.addEventListener('click', function () {
      currentCategory = pill.dataset.category;
      categoryFilters.querySelectorAll('.category-pill').forEach(function (p) {
        p.classList.toggle('active', p.dataset.category === currentCategory);
      });
      render();
    });
  });

  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        currentSearch = searchInput.value.trim();
        render();
      }, 300);
    });
  }

  if (searchClear) {
    searchClear.addEventListener('click', function () {
      searchInput.value = '';
      currentSearch = '';
      render();
      searchInput.focus();
    });
  }

  if (sortSelect) {
    sortSelect.addEventListener('change', function () {
      currentSort = sortSelect.value;
      render();
    });
  }

  // Keyboard shortcuts (unchanged from prior version)
  document.addEventListener('keydown', function (e) {
    if (!searchInput) return;
    var typing = isTypingTarget(e.target);
    if (e.key === '/' && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
      return;
    }
    if (e.key.toLowerCase() === 'k' && (e.ctrlKey || e.metaKey) && !e.altKey) {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
      return;
    }
    if (e.key === 'Escape' && document.activeElement === searchInput) {
      e.preventDefault();
      searchInput.value = '';
      currentSearch = '';
      render();
      searchInput.blur();
    }
  });
})();
```

- [ ] **Step 2: Browser smoke test**

With dev server running, visit `/`. Type into the search box: result count updates ("Showing X of Y"), × button appears, clicking × clears + restores. Click category pills — grid filters. Change sort dropdown — grid re-orders. Press `/` from anywhere — focus jumps to search.

- [ ] **Step 3: Commit**

```bash
git add backend/skills/static/skills/js/home.js
git commit -m "feat(home.js): hydrate from inline JSON; add result count + clear button"
```

---

## Task 10: Create `skill_detail` view + minimal template (TDD)

**Files:**
- Modify: `backend/skills/views.py` (add `skill_detail` view)
- Modify: `backend/skills/urls.py` (add `path('skills/<str:name>/', ...)`)
- Create: `backend/skills/templates/skills/skill_detail.html` (minimal extends-base shell)
- Create: `backend/skills/templates/skills/404.html`
- Test: `backend/skills/tests/test_views.py` (add new test functions)

- [ ] **Step 1: Write failing tests**

Append to `backend/skills/tests/test_views.py`:

```python
def test_skill_detail_renders_html(client, version_fixture):
    res = client.get('/skills/pdf/')
    assert res.status_code == 200
    assert res['Content-Type'].startswith('text/html')


def test_skill_detail_contains_skill_name(client, version_fixture):
    res = client.get('/skills/pdf/')
    body = res.content.decode('utf-8')
    assert 'pdf' in body  # name appears in the rendered HTML


def test_skill_detail_404_for_missing_skill(client, version_fixture):
    res = client.get('/skills/does-not-exist/')
    assert res.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/tests/test_views.py::test_skill_detail_renders_html skills/tests/test_views.py::test_skill_detail_404_for_missing_skill -v`
Expected: FAIL with 404 for the first (no route), 404 for the third (correctly).

- [ ] **Step 3: Add the `skill_detail` view**

In `backend/skills/views.py`, add this function (place after the `home` view from Task 7, before the JSON API divider):

```python
@require_GET
def skill_detail(request, name):
    skill = get_skills().get(name)
    if skill is None:
        from django.http import Http404
        raise Http404(f"Skill '{name}' not found")
    return render(request, 'skills/skill_detail.html', {
        'skill': skill,
        'skill_name': name,
        'install_paths': _install_paths(name),
        'version': None,
    })
```

- [ ] **Step 4: Add the URL route**

In `backend/skills/urls.py`, add the line `path('skills/<str:name>/', views.skill_detail, name='skill_detail'),` immediately after the existing `path('', views.home, name='home'),` line.

- [ ] **Step 5: Create minimal `skill_detail.html`**

Write to `backend/skills/templates/skills/skill_detail.html`:

```django
{% extends "skills/base.html" %}

{% block title %}{{ skill.name }} — Skill Market{% endblock %}

{% block body_attrs %}data-skill-name="{{ skill_name }}" data-version="{{ version|default_if_none:'' }}"{% endblock %}

{% block content %}
<main class="max-w-6xl mx-auto px-6 py-8">
  <h1 style="color:var(--text-primary)">{{ skill.name }}</h1>
  <p style="color:var(--text-secondary)">{{ skill.description }}</p>
</main>
{% endblock %}
```

- [ ] **Step 6: Create `404.html`**

Write to `backend/skills/templates/skills/404.html`:

```django
{% extends "skills/base.html" %}

{% block title %}Not found — Skill Market{% endblock %}

{% block content %}
<main class="max-w-6xl mx-auto px-6 py-12 text-center">
  <h1 class="text-2xl mb-4" style="color:var(--text-primary)">Skill not found</h1>
  <p style="color:var(--text-secondary)"><a href="/" style="color:var(--accent)">← Back to catalog</a></p>
</main>
{% endblock %}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest skills/tests/test_views.py::test_skill_detail_renders_html skills/tests/test_views.py::test_skill_detail_contains_skill_name skills/tests/test_views.py::test_skill_detail_404_for_missing_skill -v`
Expected: all 3 PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/skills/views.py backend/skills/urls.py backend/skills/templates/skills/skill_detail.html backend/skills/templates/skills/404.html backend/skills/tests/test_views.py
git commit -m "feat(skill-detail): server-render skill detail at /skills/<name>/"
```

---

## Task 11: Build full `skill_detail.html` (markdown + install modal markup)

**Files:**
- Modify: `backend/skills/templates/skills/skill_detail.html` (full replacement)

- [ ] **Step 1: Write the full skill detail template**

Replace `backend/skills/templates/skills/skill_detail.html` with:

```django
{% extends "skills/base.html" %}
{% load static %}

{% block title %}{{ skill.name }} — Skill Market{% endblock %}

{% block body_attrs %}data-skill-name="{{ skill_name }}" data-version="{{ version|default_if_none:'' }}"{% endblock %}

{% block header %}
<header class="sticky top-0 z-50 border-b px-6 py-4 flex items-center justify-between" style="background-color:var(--bg-secondary);border-color:var(--border)">
  <a href="/" title="Back to catalog (Esc)" class="flex items-center gap-2 text-sm font-medium" style="color:var(--text-secondary);text-decoration:none">
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
    </svg>
    Back
    <kbd class="text-xs px-1.5 py-0.5 rounded border ml-1" style="border-color:var(--border);font-family:inherit">Esc</kbd>
  </a>
  <button id="theme-toggle" class="p-2 rounded-lg border" style="border-color:var(--border)" aria-label="Toggle theme">
    <svg id="icon-sun" class="w-5 h-5 hidden" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 5a7 7 0 100 14 7 7 0 000-14z"/>
    </svg>
    <svg id="icon-moon" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
    </svg>
  </button>
</header>
{% endblock %}

{% block content %}
<div class="max-w-6xl mx-auto px-6 py-8">
  <div class="mb-8">
    <div class="flex items-start gap-4 mb-4">
      <span class="text-5xl">{{ skill.icon }}</span>
      <div class="flex-1">
        <div class="flex flex-wrap items-center gap-2 mb-1">
          <h1 class="text-2xl font-bold" style="color:var(--text-primary)">{{ skill.name }}</h1>
          <span class="text-sm px-2 py-0.5 rounded-full category-badge" data-category="{{ skill.category }}">{{ skill.category }}</span>
          <span class="text-xs px-2 py-0.5 rounded-full border" style="color:var(--text-secondary);border-color:var(--border)">{{ skill.license }}</span>
        </div>
        <p style="color:var(--text-secondary)">{{ skill.description }}</p>
      </div>
    </div>

    {% if skill.versions %}
    <div class="flex items-center gap-2">
      <label for="version-select" class="text-sm" style="color:var(--text-secondary)">Version:</label>
      <select id="version-select" class="text-sm rounded-lg border px-2 py-1"
        style="background-color:var(--bg-secondary);color:var(--text-primary);border-color:var(--border)">
        {% for v in skill.versions %}
          <option value="{{ v.version }}"{% if v.version == skill.currentVersion and not version %} selected{% endif %}{% if v.version == version %} selected{% endif %}>{{ v.version }}</option>
        {% endfor %}
      </select>
    </div>
    {% endif %}
  </div>

  <div class="flex flex-col lg:flex-row gap-8">
    <div class="flex-1 min-w-0">

      <section class="rounded-xl border mb-6" style="border-color:var(--border)">
        <div class="px-5 py-4 border-b" style="border-color:var(--border)">
          <h2 class="font-semibold" style="color:var(--text-primary)">Install</h2>
        </div>
        <div class="p-5">
          <div class="flex gap-2 mb-4">
            <button class="install-tab active px-3 py-1 text-sm rounded-lg font-medium" data-tab="claude">Claude Code</button>
            <button class="install-tab px-3 py-1 text-sm rounded-lg font-medium" data-tab="opencode">Opencode CLI</button>
          </div>
          <div id="tab-claude" class="install-tab-content">
            <div class="rounded-lg p-3" style="background-color:var(--bg-secondary)">
              <code class="block text-sm break-all" style="color:var(--text-primary)">cp -r &lt;repo&gt;/{{ skill.name }} {{ install_paths.claudeCode }}</code>
            </div>
          </div>
          <div id="tab-opencode" class="install-tab-content hidden">
            <div class="rounded-lg p-3" style="background-color:var(--bg-secondary)">
              <code class="block text-sm break-all" style="color:var(--text-primary)">cp -r &lt;repo&gt;/{{ skill.name }} {{ install_paths.opencode }}</code>
            </div>
          </div>
        </div>
      </section>

      <section class="rounded-xl border mb-6" style="border-color:var(--border)">
        <div class="px-5 py-4 border-b" style="border-color:var(--border)">
          <h2 class="font-semibold" style="color:var(--text-primary)">Documentation</h2>
        </div>
        <div class="p-5 skill-markdown">{{ skill.contentHtml|safe }}</div>
      </section>

      <section id="files-section" class="rounded-xl border hidden" style="border-color:var(--border)">
        <div class="px-5 py-4 border-b" style="border-color:var(--border)">
          <h2 class="font-semibold" style="color:var(--text-primary)">Files</h2>
        </div>
        <div id="files-list" class="divide-y" style="border-color:var(--border)"></div>
      </section>

    </div>

    <div class="lg:w-72 flex-shrink-0 space-y-4">
      <div class="rounded-xl border p-5" style="border-color:var(--border);background-color:var(--bg-card)">
        <h3 class="font-semibold mb-4" style="color:var(--text-primary)">Details</h3>
        <dl class="space-y-3 text-sm">
          <div class="flex justify-between"><dt style="color:var(--text-secondary)">Files</dt><dd style="color:var(--text-primary)">{{ skill.fileCount }}</dd></div>
          <div class="flex justify-between gap-4"><dt class="shrink-0" style="color:var(--text-secondary)">License</dt><dd class="text-right" style="color:var(--text-primary)">{{ skill.license }}</dd></div>
          <div class="flex justify-between"><dt style="color:var(--text-secondary)">Updated</dt><dd style="color:var(--text-primary)">{{ skill.lastUpdated|slice:":10" }}</dd></div>
          <div class="flex justify-between"><dt style="color:var(--text-secondary)">Category</dt><dd style="color:var(--text-primary)">{{ skill.category }}</dd></div>
        </dl>
      </div>

      <div class="rounded-xl border p-5" style="border-color:var(--border);background-color:var(--bg-card)">
        <h3 class="font-semibold mb-4" style="color:var(--text-primary)">Install Paths</h3>
        <div class="space-y-3 text-sm">
          <div><p class="mb-1" style="color:var(--text-secondary)">Claude Code</p><code class="text-xs break-all" style="color:var(--text-primary)">{{ install_paths.claudeCode }}</code></div>
          <div><p class="mb-1" style="color:var(--text-secondary)">Opencode CLI</p><code class="text-xs break-all" style="color:var(--text-primary)">{{ install_paths.opencode }}</code></div>
        </div>
      </div>

      <button id="install-button"
        class="flex items-center justify-center gap-2 w-full py-3 px-4 rounded-xl font-medium text-sm text-white"
        style="background-color:var(--accent)" title="Install to /AAA/<user>/skills/">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v12m0 0l-4-4m4 4l4-4M4 20h16"/></svg>
        Install
      </button>

      <a id="download-link"
        href="{% if version %}/api/skills/{{ skill_name }}/versions/{{ version }}/zip{% else %}/api/skills/{{ skill_name }}/zip{% endif %}"
        title="Download ZIP (D)"
        class="flex items-center justify-center gap-2 w-full py-3 px-4 rounded-xl font-medium text-sm text-white"
        style="background-color:var(--accent)">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
        Download ZIP
        <kbd class="text-xs px-1.5 py-0.5 rounded border ml-1" style="border-color:rgba(255,255,255,0.4);font-family:inherit">D</kbd>
      </a>
    </div>
  </div>
</div>

<!-- Install modal — styled fully via app.css (.install-modal-* classes). -->
<div id="install-modal" class="install-modal hidden" role="dialog"
     aria-modal="true" aria-labelledby="install-modal-title">
  <div class="install-modal-card">
    <button id="install-modal-close" class="install-modal-close" type="button" aria-label="Close">×</button>
    <p class="install-modal-kicker">Install</p>
    <h3 id="install-modal-title" class="install-modal-title">{{ skill.name }}</h3>
    <p class="install-modal-userline">
      <span>Deploying as</span>
      <span id="install-modal-user" class="install-modal-userchip">—</span>
    </p>
    <p id="install-modal-no-cookie" class="install-modal-warning hidden">
      No <code style="font-family:inherit;font-weight:700">CURRENT_USER_NAME</code> cookie — install requires a logged-in session.
    </p>
    <p class="install-modal-section">Choose target</p>
    <div id="install-modal-targets" class="install-modal-targets"></div>
    <div id="install-modal-result" class="install-modal-result hidden"></div>
    <div class="install-modal-actions">
      <button id="install-modal-cancel" class="install-modal-btn" type="button">Cancel</button>
    </div>
  </div>
</div>
{% endblock %}

{% block extra_scripts %}
<script src="{% static 'skills/vendor/highlight.min.js' %}"></script>
<script src="{% static 'skills/js/skill.js' %}"></script>
{% endblock %}
```

- [ ] **Step 2: Browser smoke test**

Visit `http://localhost:8888/skills/pdf/` (or any real skill name). Confirm: title, category, license badge, two-column layout, install panel with command box, **rendered markdown** (headings, paragraphs visible), details/install-paths sidebar, install button, download link. The install modal markup is present but hidden — verify with DevTools that `#install-modal` exists. Right-click → View Source: markdown is rendered to HTML in the source.

- [ ] **Step 3: Commit**

```bash
git add backend/skills/templates/skills/skill_detail.html
git commit -m "feat(skill-detail): full template with server-rendered markdown + install modal"
```

---

## Task 12: Update `skill.js` — drop hash routing, use data attrs, lazy file fetch

**Files:**
- Modify: `backend/skills/static/skills/js/skill.js` (full replacement)

- [ ] **Step 1: Replace the file**

Write the new content to `backend/skills/static/skills/js/skill.js`:

```javascript
'use strict';

(function () {
  var skillName = document.body.dataset.skillName || '';
  var version = document.body.dataset.version || '';

  if (!skillName) return;

  // Syntax-highlight server-rendered markdown code blocks (fenced code in
  // contentHtml) immediately. hljs is loaded before this script.
  if (window.hljs && window.hljs.highlightAll) window.hljs.highlightAll();

  // -------------------------------------------------------------------------
  // URL builders
  // -------------------------------------------------------------------------

  function filesUrl() {
    return version
      ? '/api/skills/' + encodeURIComponent(skillName) + '/versions/' + encodeURIComponent(version) + '/files'
      : '/api/skills/' + encodeURIComponent(skillName) + '/files';
  }

  function installPostUrl() {
    return version
      ? '/api/skills/' + encodeURIComponent(skillName) + '/versions/' + encodeURIComponent(version) + '/install'
      : '/api/skills/' + encodeURIComponent(skillName) + '/install';
  }

  // -------------------------------------------------------------------------
  // Install modal (preserve existing behavior verbatim)
  // -------------------------------------------------------------------------

  function getCookie(name) {
    var match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : '';
  }

  function fetchInstallTargets() {
    return fetch('/api/install/targets')
      .then(function (res) { return res.ok ? res.json() : { targets: [] }; })
      .then(function (data) { return data.targets || []; })
      .catch(function () { return []; });
  }

  function openInstallModal() {
    var modal = document.getElementById('install-modal');
    var titleEl = document.getElementById('install-modal-title');
    var userEl = document.getElementById('install-modal-user');
    var noCookieEl = document.getElementById('install-modal-no-cookie');
    var targetsEl = document.getElementById('install-modal-targets');
    var resultEl = document.getElementById('install-modal-result');
    var cancelBtn = document.getElementById('install-modal-cancel');
    var closeBtn = document.getElementById('install-modal-close');

    var user = getCookie('CURRENT_USER_NAME');
    titleEl.textContent = skillName;
    userEl.textContent = user || 'no session';
    resultEl.classList.add('hidden');
    resultEl.classList.remove('is-ok', 'is-err');
    resultEl.textContent = '';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.disabled = false;
    noCookieEl.classList.toggle('hidden', !!user);
    targetsEl.innerHTML = '';

    fetchInstallTargets().then(function (targets) {
      if (!targets.length) {
        var empty = document.createElement('p');
        empty.style.color = 'var(--text-secondary)';
        empty.style.fontSize = '0.85rem';
        empty.style.margin = '0';
        empty.textContent = 'No install targets configured — set INSTALL_TARGET_* env vars on the backend.';
        targetsEl.appendChild(empty);
        return;
      }
      targets.forEach(function (t) {
        var path = (user ? t.base.replace('{user_name}', user) : t.base.replace('{user_name}', '<user>')) + '/' + skillName;
        var row = document.createElement('button');
        row.type = 'button';
        row.className = 'install-target-btn';
        row.disabled = !user;
        row.innerHTML =
          '<span class="install-target-name">' + escapeHtml(t.name) + '</span>' +
          '<span class="install-target-path">' + escapeHtml(path) + '</span>' +
          '<span class="install-target-go">&rarr;</span>';
        row.onclick = function () { performInstall(t.name, row); };
        targetsEl.appendChild(row);
      });
    });

    cancelBtn.onclick = closeInstallModal;
    closeBtn.onclick = closeInstallModal;
    modal.classList.remove('hidden');
    requestAnimationFrame(function () { modal.classList.add('is-open'); });
  }

  function closeInstallModal() {
    var modal = document.getElementById('install-modal');
    modal.classList.remove('is-open');
    setTimeout(function () { modal.classList.add('hidden'); }, 220);
  }

  function performInstall(targetName, row) {
    var resultEl = document.getElementById('install-modal-result');
    var cancelBtn = document.getElementById('install-modal-cancel');
    var targetsEl = document.getElementById('install-modal-targets');
    Array.prototype.forEach.call(targetsEl.querySelectorAll('.install-target-btn'), function (b) { b.disabled = true; });
    row.dataset.state = 'busy';
    row.querySelector('.install-target-go').innerHTML = '⏳';

    fetch(installPostUrl(), {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: targetName }),
    })
      .then(function (res) {
        return res.json().then(function (data) { return { ok: res.ok, data: data }; });
      })
      .then(function (r) {
        if (r.ok && r.data.status === 'ok') {
          row.dataset.state = 'ok';
          row.querySelector('.install-target-go').innerHTML = '✓';
          resultEl.textContent = '✓ Installed to ' + r.data.target + ' — ' + r.data.path;
          resultEl.classList.add('is-ok');
        } else {
          row.dataset.state = 'err';
          row.querySelector('.install-target-go').innerHTML = '✗';
          resultEl.textContent = '✗ ' + (r.data.error || 'Install failed');
          resultEl.classList.add('is-err');
        }
        resultEl.classList.remove('hidden');
        cancelBtn.textContent = 'Close';
      })
      .catch(function (err) {
        row.dataset.state = 'err';
        row.querySelector('.install-target-go').innerHTML = '✗';
        resultEl.textContent = '✗ Network error — ' + err.message;
        resultEl.classList.add('is-err');
        resultEl.classList.remove('hidden');
        cancelBtn.textContent = 'Close';
      });
  }

  // -------------------------------------------------------------------------
  // Install tabs
  // -------------------------------------------------------------------------

  Array.prototype.forEach.call(document.querySelectorAll('.install-tab'), function (tab) {
    tab.addEventListener('click', function () {
      var name = tab.dataset.tab;
      document.querySelectorAll('.install-tab').forEach(function (t) {
        t.classList.toggle('active', t.dataset.tab === name);
      });
      document.querySelectorAll('.install-tab-content').forEach(function (c) {
        c.classList.toggle('hidden', c.id !== 'tab-' + name);
      });
    });
  });

  // -------------------------------------------------------------------------
  // Version selector (path navigation)
  // -------------------------------------------------------------------------

  var versionSelect = document.getElementById('version-select');
  if (versionSelect) {
    versionSelect.addEventListener('change', function () {
      var v = versionSelect.value;
      window.location.href = '/skills/' + encodeURIComponent(skillName) + '/v/' + encodeURIComponent(v) + '/';
    });
  }

  // -------------------------------------------------------------------------
  // File viewer (lazy from /api/skills/<name>/files)
  // -------------------------------------------------------------------------

  function renderFiles(files) {
    var section = document.getElementById('files-section');
    var list = document.getElementById('files-list');
    if (!files || !files.length) return;
    section.classList.remove('hidden');
    list.innerHTML = files.map(function (f) {
      var content = f.truncated || f.content === null
        ? '<p style="color:var(--text-secondary);font-style:italic;padding:1rem">File too large to display.</p>'
        : '<pre><code class="hljs">' + escapeHtml(f.content || '') + '</code></pre>';
      return (
        '<details class="px-5 py-3"><summary style="cursor:pointer;color:var(--text-primary)">' +
          escapeHtml(f.path) +
        '</summary><div class="mt-3">' + content + '</div></details>'
      );
    }).join('');
    if (window.hljs && window.hljs.highlightAll) window.hljs.highlightAll();
  }

  fetch(filesUrl())
    .then(function (res) { return res.ok ? res.json() : []; })
    .then(renderFiles)
    .catch(function () { /* silent — files section just stays hidden */ });

  // -------------------------------------------------------------------------
  // Install button
  // -------------------------------------------------------------------------

  var installBtn = document.getElementById('install-button');
  if (installBtn) installBtn.onclick = openInstallModal;

  // -------------------------------------------------------------------------
  // Keyboard shortcuts
  //   Esc → back to catalog
  //   D   → trigger download link
  // -------------------------------------------------------------------------

  document.addEventListener('keydown', function (e) {
    if (isTypingTarget(e.target)) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    if (e.key === 'Escape') {
      e.preventDefault();
      window.location.href = '/';
      return;
    }
    if (e.key === 'd' || e.key === 'D') {
      var link = document.getElementById('download-link');
      if (!link) return;
      e.preventDefault();
      link.click();
    }
  });
})();
```

- [ ] **Step 2: Browser smoke test**

Visit `/skills/pdf/`. Verify: install button opens modal; modal shows targets; cancel closes; download link works (downloads zip); pressing `D` triggers the download; pressing `Esc` navigates back to `/`. Files section appears below the documentation with collapsible `<details>` per file, syntax-highlighted.

- [ ] **Step 3: Run the install-modal audit**

Open `/skills/<some-skill>/` in the browser. Open DevTools console. Read the file `backend/skills/static/skills/dev/install-modal-ui-audit.js`, paste its contents into the console, and run the audit. Expected: returns `{passed: 64+, failed: 0}`. (If it fails on a positioning assertion, the modal CSS may be loading from the wrong path — check `Network` tab for `app.css`.)

- [ ] **Step 4: Commit**

```bash
git add backend/skills/static/skills/js/skill.js
git commit -m "feat(skill.js): drop hash routing; use data-skill-name; lazy file fetch"
```

---

## Task 13: Wire version routes (TDD)

**Files:**
- Modify: `backend/skills/views.py` (add `skill_detail_version`)
- Modify: `backend/skills/urls.py` (add version path)
- Test: `backend/skills/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Append to `backend/skills/tests/test_views.py`:

```python
def test_version_detail_renders_html(client, version_fixture):
    res = client.get('/skills/webapp-testing/v/20260331-version-test/')
    assert res.status_code == 200
    body = res.content.decode('utf-8')
    assert 'webapp-testing' in body


def test_version_detail_404_for_missing_version(client, version_fixture):
    res = client.get('/skills/webapp-testing/v/99999999-fake/')
    assert res.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/tests/test_views.py::test_version_detail_renders_html skills/tests/test_views.py::test_version_detail_404_for_missing_version -v`
Expected: 404 on the route (not yet defined).

- [ ] **Step 3: Add the view**

In `backend/skills/views.py`, add (next to `skill_detail`):

```python
@require_GET
def skill_detail_version(request, name, version):
    skill = get_skills().get(name)
    if skill is None:
        from django.http import Http404
        raise Http404(f"Skill '{name}' not found")
    ver_dir = _version_dir(name, version)
    if ver_dir is None:
        from django.http import Http404
        raise Http404(f"Version '{version}' not found")
    if version == 'original':
        ver_skill = parse_skill(ver_dir, name)
    else:
        ver_skill = _parse_version_dir(ver_dir, name)
    if ver_skill is None:
        from django.http import Http404
        raise Http404(f"Version '{version}' not found")
    return render(request, 'skills/skill_detail.html', {
        'skill': ver_skill,
        'skill_name': name,
        'install_paths': _install_paths(name),
        'version': version,
    })
```

- [ ] **Step 4: Add the URL**

In `backend/skills/urls.py`, immediately after the line `path('skills/<str:name>/', views.skill_detail, ...)`, add:

```python
path('skills/<str:name>/v/<str:version>/', views.skill_detail_version, name='skill_detail_version'),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest skills/tests/test_views.py::test_version_detail_renders_html skills/tests/test_views.py::test_version_detail_404_for_missing_version -v`
Expected: both PASS.

- [ ] **Step 6: Browser smoke test**

Visit a versioned skill (the test fixture creates `webapp-testing/20260331-version-test`). Use the version dropdown — confirm navigation goes to `/skills/webapp-testing/v/<version>/`. The "original" option should also work and navigate to `/skills/webapp-testing/v/original/`.

- [ ] **Step 7: Commit**

```bash
git add backend/skills/views.py backend/skills/urls.py backend/skills/tests/test_views.py
git commit -m "feat(versions): add /skills/<name>/v/<version>/ route + view"
```

---

## Task 14: Drop legacy routes, `frontend/`, and `FRONTEND_DIR`

**Files:**
- Modify: `backend/skills/views.py` (remove `_read_shell`, `index_shell`, `skill_shell`)
- Modify: `backend/skills/urls.py` (remove legacy routes + static `re_path`)
- Modify: `backend/skill_market/settings.py` (remove `FRONTEND_DIR` + `STATICFILES_DIRS`)
- Delete: `frontend/` directory
- Modify: `backend/skills/tests/test_views.py` (remove tests for legacy `/index.html`, `/skill.html` if any)

- [ ] **Step 1: Remove legacy view functions**

In `backend/skills/views.py`, delete the entire block (currently around lines 55-75):

```python
# ---------------------------------------------------------------------------
# HTML shells — return the static frontend HTML as-is (no templating)
# ---------------------------------------------------------------------------

def _read_shell(filename):
    ...

@require_GET
def index_shell(request):
    return _read_shell('index.html')


@require_GET
def skill_shell(request):
    ...
    return _read_shell('skill.html')
```

- [ ] **Step 2: Prune URL routes**

In `backend/skills/urls.py`, delete:
- The line `path('index.html', views.index_shell),`
- The line `path('skill.html', views.skill_shell, name='skill_detail'),`
- The entire `re_path(r'^(?P<path>(?:vendor|assets)/.+|config\.js)$', static_serve, ...)` block
- The unused imports `from django.urls import ..., re_path` (drop `re_path`) and `from django.views.static import serve as static_serve`

- [ ] **Step 3: Strip `FRONTEND_DIR` from settings**

In `backend/skill_market/settings.py`, delete:
- The line `FRONTEND_DIR = Path(os.environ.get('FRONTEND_DIR', str(BASE_DIR.parent / 'frontend')))`
- The line `STATICFILES_DIRS = [FRONTEND_DIR]`

- [ ] **Step 4: Search for any remaining `frontend/` or `FRONTEND_DIR` references**

Run (from repo root): `git grep -n -e "FRONTEND_DIR" -e "frontend/" -e "config\.js"`
Expected results and how to clean each:
- `CLAUDE.md` — cleaned up in Task 15
- `README.md` — already noted as stale; leave alone or update prose
- `backend/start.sh` — remove any `cd frontend` or `FRONTEND_DIR=...` lines
- `backend/ecosystem.config.cjs` — remove any `FRONTEND_DIR` env or `frontend/` cwd reference
- `backend/.env.example` — delete the `FRONTEND_DIR=./frontend` line and its comment block
- `backend/.env.production.example` — same: remove any `FRONTEND_DIR` line
- `DEPLOY.md` — remove or update any paragraph referencing `frontend/` or `FRONTEND_DIR`
- Historical docs under `docs/archive/`, `docs/superpowers/plans/` — leave alone

- [ ] **Step 5: Delete `frontend/`**

Run: `git rm -r frontend/`
Expected: removes the now-empty `frontend/assets/`, `frontend/vendor/`, `frontend/dev/`, plus `frontend/index.html`, `frontend/skill.html`, `frontend/config.js`.

- [ ] **Step 6: Run all unit tests**

Run (from `backend/`): `pytest -v`
Expected: all green. Before running, **delete these two now-stale tests** from `backend/skills/tests/test_views.py`:
- `test_home_page_renders` (line ~344) — asserts `b'Skill Market'` against `/`; replaced by `test_home_renders_html` from Task 7
- `test_detail_page_renders` (line ~350) — fetches `/skill.html` and asserts `b'skill-root'`; neither the route nor the element exist after this task

Do not just update URLs — the assertions (`b'skill-root'`) are also stale and will still fail.

- [ ] **Step 7: Browser smoke test (full pass)**

Restart `./backend/start.sh`. Walk through:
1. `/` — catalog renders, search/filter/sort work
2. `/skills/<name>/` — detail page renders, install modal works
3. `/skills/<versioned>/v/<version>/` — version detail works
4. `/skills/does-not-exist/` — 404 page
5. `/skill.html` and `/index.html` — should now both 404 (legacy routes gone)

Both light and dark themes per `feedback_ui_verify_visually.md`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: drop legacy frontend/ shell routes and FRONTEND_DIR setting"
```

---

## Task 15: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the "Stack note" section**

Open `CLAUDE.md`. Replace the "Stack note (README is stale)" section's body. The current text says the frontend is "static HTML + vanilla JS in `frontend/`" with "no frontend build step" and mentions the directory is "deployable on its own". Replace with:

```markdown
## Stack note (README is stale)

`README.md` describes a Node/Express + React/Vite stack with `node manage.js` commands. That stack has been replaced. The running app is **Django 5.x** with frontend served via Django templates from the `skills` app (`backend/skills/templates/skills/{base,home,skill_detail,404}.html`). Static assets live under `backend/skills/static/skills/...` and are picked up by Django's `APP_DIRS=True` static finder, then served by WhiteNoise. There is no frontend build step — vendored Tailwind and highlight.js live in `backend/skills/static/skills/vendor/`. SKILL.md markdown is pre-rendered to HTML in `parser.py` (the `contentHtml` field) and emitted in templates via `{{ skill.contentHtml|safe }}`.
```

- [ ] **Step 2: Remove the split-deploy paragraph**

The current `CLAUDE.md` has a paragraph starting `The frontend/ directory is **deployable on its own**:` — delete it entirely.

- [ ] **Step 3: Update the "Statics & frontend" section**

Replace it with:

```markdown
**Statics & frontend.** Static assets live in `backend/skills/static/skills/` and are picked up by `django.contrib.staticfiles` via `APP_DIRS=True`. WhiteNoise serves them in production after `collectstatic` populates `staticfiles/`. Templates live in `backend/skills/templates/skills/`. There is no `FRONTEND_DIR` environment variable, no `config.js`, and no separate static deploy — all paths resolve through `{% static %}`.
```

- [ ] **Step 4: Update the env-loading section**

Find the bullet list of env vars that mentions `INSTALL_TARGET_*`. Remove `FRONTEND_DIR` from any list. Drop the line about `config.js` overrides if present.

- [ ] **Step 5: Update the URL conventions section**

Add a sentence: `HTML routes are /, /skills/<name>/, /skills/<name>/v/<version>/. The /index.html and /skill.html shell routes were removed in the Django-templates migration.`

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(CLAUDE): document Django-templates frontend; drop split-deploy notes"
```

---

## Task 16: Update Playwright e2e tests

**Files:**
- Modify: `backend/e2e/*.py` (URLs)

- [ ] **Step 1: Find e2e tests that reference legacy URLs**

Run: `git grep -n -e "skill\.html" -e "index\.html" backend/e2e/`
Expected: lists every line that needs updating.

- [ ] **Step 2: Update each match**

For each match:
- Replace `skill.html#<name>` (or `skill.html?name=<name>`) with `/skills/<name>/`
- Replace `index.html` with `/`

- [ ] **Step 3: Add a server-rendering assertion**

Pick the most central e2e test (probably one that loads a skill detail page) and add an assertion that the skill name appears in the **initial** page response — i.e., before any JS executes. With Playwright:

```python
# After page.goto('/skills/pdf/'):
content_before_js = page.content()  # at this point JS has run; instead use response body:
response = page.context.request.get('/skills/pdf/')
assert 'pdf' in response.text()
```

(If the existing test framework doesn't make raw-response assertions easy, a simpler proxy is `expect(page.locator('h1')).to_have_text('pdf')` immediately after navigate — but the request-text approach is more rigorous.)

- [ ] **Step 4: Run e2e**

Run (from `backend/`): `pytest e2e/ -v`
Expected: all pass. If Playwright's bundled Chromium is missing on this machine, set `CHROMIUM_EXEC=/path/to/chrome` per `CLAUDE.md`.

- [ ] **Step 5: Commit**

```bash
git add backend/e2e/
git commit -m "test(e2e): update Playwright URLs to new path-routed scheme"
```

---

## Task 17: Final verification pass

**Files:** none (verification only)

- [ ] **Step 1: Run full unit test suite**

Run (from `backend/`): `pytest -v`
Expected: all green.

- [ ] **Step 2: Run e2e**

Run (from `backend/`): `pytest e2e/ -v`
Expected: all green.

- [ ] **Step 3: `collectstatic` succeeds**

Run (from `backend/`): `backend/venv/Scripts/python manage.py collectstatic --noinput`
Expected: succeeds; output mentions files copied from the new `backend/skills/static/skills/` location.

- [ ] **Step 4: Manual click-through, both themes**

Per `feedback_ui_verify_visually.md`, walk through the app in both light and dark modes:
- `/` — catalog, search ("Showing X of Y" updates), × button works, category pills filter, sort dropdown re-orders
- `/skills/<name>/` — full detail page, theme toggle persists across navigation
- Open install modal — targets list, install completes (or shows no-cookie warning if no `CURRENT_USER_NAME`)
- Press `D` — ZIP downloads
- Press `Esc` — returns to catalog
- Versioned skill — switch versions via dropdown; URL updates to `/skills/<name>/v/<v>/`

- [ ] **Step 5: Run install-modal audit**

Open `/skills/<some-skill>/` → DevTools console → paste `backend/skills/static/skills/dev/install-modal-ui-audit.js` → run.
Expected: `{passed: 64+, failed: 0}`.

- [ ] **Step 6: Pre-merge checklist (no commit needed; just verify)**

- [ ] `frontend/` directory is gone (`ls frontend/` → not found)
- [ ] No `FRONTEND_DIR` references remain (`git grep FRONTEND_DIR` returns nothing)
- [ ] No `config.js` references remain (`git grep config\.js` returns nothing)
- [ ] CLAUDE.md updated (stack note, statics section, env-loading section)
- [ ] All unit tests pass
- [ ] All e2e tests pass
- [ ] Manual visual verification done in both themes

- [ ] **Step 7: Push the branch and open the PR**

Run:
```bash
git push -u origin feature/django-templates
```

Then open a PR with the title `Django templates migration` and a body that links to `docs/superpowers/specs/2026-05-05-django-templates-migration-design.md` for the full rationale, lists the 17 commits at a high level, and explicitly notes the deferred UI/UX items (#1, #2, #5) with links/issue numbers if applicable.

---

## Notes for the executing engineer

- **Each task is independently committable.** If you have to stop mid-plan, the branch is in a runnable state at the end of every task.
- **TDD is enforced for parser, view, and route changes** (Tasks 3, 7, 10, 13). Skip the test-first step at your peril — the watcher and route layer have non-obvious failure modes that tests catch quickly.
- **Don't refactor `skill.js` or `home.js` while migrating them.** This plan preserves existing behavior except where explicitly noted (item #3 first-paint, item #4 search affordances, hash-to-path routing). Keep the diff focused.
- **JIT-purged Tailwind warning still applies.** Any new utility class (e.g. `.fixed`, `.inset-0`) on a new element will silently fail unless that class is already in `vendor/tailwind.min.css`. The templates above were carefully constructed to reuse classes that exist on other elements in the source HTML. If a layout looks broken, check the bundle — use inline `style=""` instead.
- **Items #1, #2, #5 are deferred** and *not* fixed by this migration. Don't try to fix them here — separate branches.
- **Don't touch the `/api/*` surface.** All API views are preserved as-is, including the now-vestigial `/api/skills/<name>` JSON detail endpoint. Removing those is follow-up cleanup, not part of this plan.
