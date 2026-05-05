# Django Templates Migration — skill-manager

## Context

The frontend is currently plain HTML files in `frontend/` served by Django via two `read()`-and-return view functions (`backend/skills/views.py:65-75`). All page content is hydrated client-side from `/api/*` after page load: `home.js` fetches `/api/skills` and renders the catalog; `skill.js` reads the URL hash, fetches `/api/skills/<name>` plus `/api/skills/<name>/files`, and populates the detail page.

The user wants a new branch where the frontend uses **Django templates** instead of static HTML. They confirmed split-deploy is no longer a goal, so the "frontend deployable on its own" property of the current layout can be dropped. Two UI/UX issues from the prior review become essentially free to fix during this migration and will be folded in:

- **Item #3** — loading/error UX (template can render skeleton + first paint synchronously, eliminating the blank-grid flash)
- **Item #4** — search lacks accessible label, result count, clear button (`index.html` is being rewritten anyway)

Items #1 (modal Escape collision), #2 (modal focus management), and #5 (state semantics + contrast + focus-visible) are **not** in scope for this branch — they are surgical JS/CSS fixes that can land on `master` independently and would only inflate the review surface here.

### Decisions locked in

| Area | Decision |
| --- | --- |
| Render strategy | **Hybrid** — template renders shell + first paint; existing JS hydrates from API |
| Skill detail URLs | **Path routing** — `/skills/<name>/` and `/skills/<name>/v/<version>/`; hash routing dropped |
| Markdown / highlighting | **Markdown server-side** (Python `markdown` lib, prerendered in the watcher); **highlight.js stays client-side** for the file viewer |
| File contents | **Lazy via API** — template renders metadata only; JS keeps fetching `/api/skills/<name>/files` |
| UI/UX scope | Migration **+ #3 + #4**. Defer #1, #2, #5 to follow-up branches |
| Branch name | `feature/django-templates` (proposed; rename freely) |

---

## Target architecture

```
backend/
  skill_market/
    settings.py            ← add TEMPLATES; keep STATICFILES_DIRS
  skills/
    templates/skills/
      base.html            ← <html>, <head>, header, theme bootstrap, footer
      home.html            ← extends base; catalog with skeleton first paint
      skill_detail.html    ← extends base; metadata + markdown server-rendered
    static/skills/         ← migrate frontend/assets/ + frontend/vendor/ here
      css/app.css
      css/pygments.css     (only if pygments ever used; not used now)
      js/common.js
      js/home.js           ← shrinks: search count, clear button, no JSON-driven render of static fields
      js/skill.js          ← shrinks: install modal + tabs + file fetch only
      vendor/tailwind.min.css, highlight.min.css, highlight.min.js
    parser.py              ← add contentHtml via markdown.markdown(...)
    urls.py                ← new HTML routes; /skill.html and # routing dropped
    views.py               ← new HTML views replace read-shell views; API kept
  requirements*.txt        ← add markdown
frontend/                  ← directory deleted at end of migration; nothing references it
```

The `frontend/` directory is **deleted** once templates land. `STATICFILES_DIRS` is dropped (or pointed at the new app-level `static/` if needed). `FRONTEND_DIR` env var becomes vestigial — remove from settings, `.env*` examples, `start.sh` if referenced. The `vendor/assets/config.js` `re_path` hack in `urls.py:17-21` goes away; templates use `{% static %}` and there is no `config.js` anymore (no split deploy).

### What the JS still does after migration

- **`common.js`** — unchanged. Theme toggle, `relativeTime`, `escapeHtml`, `isTypingTarget`.
- **`home.js`** — keeps the live filter/search/sort path against the existing `/api/skills` fetch, but the *first paint* (skeleton cards + chrome + `<h1>` + stat counters) comes from the template. After hydration, JS replaces the skeleton with rendered cards. The catalog still uses the API on every keystroke (snappy, debounced, current behavior). Adds: `aria-label` already in template, result-count update, clear-button toggle.
- **`skill.js`** — drops `parseHash()` and the `hashchange` listener. Reads skill name from a `data-skill-name` attribute on `<body>` (set by template). Only client-side responsibilities remaining: open/close install modal, install target POST, install tab switching, fetch and render `/api/skills/<name>/files` (or version variant) into the file viewer with highlight.js. Version dropdown now navigates by `window.location` to `/skills/<name>/v/<version>/` (real navigation, no in-page reload).

### Markdown rendering pipeline

`parser.parse_skill_from_dir()` already loads `SKILL.md` into `post.content` (`parser.py:90`). Add a sibling key:

```python
import markdown
...
'content': post.content,
'contentHtml': markdown.markdown(post.content, extensions=['fenced_code', 'tables']),
```

Rendered once per parse. The watcher debounce (300ms in `watcher.py`) means edits to a SKILL.md re-parse and re-render automatically. Templates emit `{{ skill.contentHtml|safe }}` inside the documentation section. The existing markdown-class stylesheet in `app.css` already targets the resulting tag tree (`h1-h4`, `p`, `ul/ol`, `code`, `pre`, `table`, `blockquote`, `a`) so no CSS rewrite is needed.

Bleach/HTML sanitization is **not** required: SKILL.md content is curated repo content, not user-submitted input. Document this in a one-line comment near the `markdown.markdown(...)` call so the next maintainer knows.

---

## Concrete changes by file

### `backend/skill_market/settings.py`

- Add a `TEMPLATES` setting (currently absent — Django's default template engine is unconfigured):
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
- Drop `FRONTEND_DIR` and `STATICFILES_DIRS = [FRONTEND_DIR]`. Move static assets into `backend/skills/static/skills/...` so `APP_DIRS=True` static finder picks them up.
- Keep `STATIC_URL`, `STATIC_ROOT`, `WHITENOISE_MANIFEST_STRICT = False`.

### `backend/skills/urls.py`

Replace the HTML-shell + static `re_path` block with:

```python
path('', views.home, name='home'),
path('skills/<str:name>/', views.skill_detail, name='skill_detail'),
path('skills/<str:name>/v/<str:version>/', views.skill_detail_version, name='skill_detail_version'),
```

Keep all `api/*` routes as-is. Drop `path('index.html', ...)`, `path('skill.html', ...)`, and the `(?P<path>(?:vendor|assets)/.+|config\.js)` `re_path` (WhiteNoise + `{% static %}` handle assets).

### `backend/skills/views.py`

Replace `_read_shell`, `index_shell`, `skill_shell` with:

```python
from django.shortcuts import render
from django.http import Http404

@require_GET
def home(request):
    skills = list(get_skills().values())
    return render(request, 'skills/home.html', {
        'skills': skills,
        'skills_json': json.dumps(skills),  # for the in-page <script type="application/json"> hydration cache
        'categories': get_categories(get_skills()),
    })

@require_GET
def skill_detail(request, name):
    skill = get_skills().get(name)
    if skill is None:
        raise Http404(f"Skill '{name}' not found")
    return render(request, 'skills/skill_detail.html', {
        'skill': skill,
        'skill_name': name,
        'install_paths': _install_paths(name),
        'version': None,
    })

@require_GET
def skill_detail_version(request, name, version):
    skill = get_skills().get(name)
    if skill is None:
        raise Http404(f"Skill '{name}' not found")
    ver_dir = _version_dir(name, version)
    if ver_dir is None:
        raise Http404(f"Version '{version}' not found")
    ver_skill = parse_skill(ver_dir, name) if version == 'original' else _parse_version_dir(ver_dir, name)
    if ver_skill is None:
        raise Http404(f"Version '{version}' not found")
    return render(request, 'skills/skill_detail.html', {
        'skill': ver_skill,
        'skill_name': name,
        'install_paths': _install_paths(name),
        'version': version,
    })
```

Reuse existing helpers `_install_paths`, `_version_dir`, `_parse_version_dir`. Keep all `api_*` view functions untouched. Add a 404 template `skills/404.html` for the not-found case.

### `backend/skills/templates/skills/`

- **`base.html`** — Owns `<html>`, theme-bootstrap `<script>` (current pattern in `frontend/index.html` head), header (logo + theme toggle), footer, `{% block content %}`. The header search is *only* on the home page, so it goes in `home.html` not `base.html`.
- **`home.html`** — Extends `base.html`. Renders:
  - Hero with stats (`{{ skills|length }}`, `{{ categories|length }}`)
  - Search input with proper `<label>`, result-count `<span>` (initially `"Showing N of N"`), clear-button (initially hidden)
  - Category filter pills via `{% for c in categories %}`
  - Sort dropdown
  - **Skill grid skeleton**: render the actual skill cards directly (server-rendered first paint), no skeleton placeholder needed because data is in `_skills` dict and the response is fast. JS rewrites the same DOM during filter/sort. (This is the loading-UX win — no fetch-then-render flash on first load.)
  - `#no-results`, `#load-error` (kept for JS-side filter empty states; load-error becomes "Refresh failed" since initial paint can't fail)
- **`skill_detail.html`** — Extends `base.html`. Renders:
  - Header with back link, version selector (`<select>` whose `onchange` navigates to `/skills/<name>/v/<value>/`)
  - Two-column layout matching current `frontend/skill.html`
  - Left column: install command tabs (Claude Code / Opencode CLI), `{{ skill.contentHtml|safe }}` for documentation, `<div id="files-container">` placeholder for JS-loaded files
  - Right sidebar: details card (file count, license, updated, category), install paths card, install button, download link
  - Install modal (current markup from `skill.html:167-220`, copied verbatim — preserve `aria-modal`, custom `.install-modal-*` classes, JIT-purge-safe inline styles)
- **`404.html`** — minimal "Skill not found" page extending `base.html`.

### `backend/skills/static/skills/`

Move (don't copy) the contents of `frontend/`:
- `frontend/assets/app.css` → `backend/skills/static/skills/css/app.css`
- `frontend/assets/common.js` → `backend/skills/static/skills/js/common.js`
- `frontend/assets/home.js` → `backend/skills/static/skills/js/home.js` (with edits below)
- `frontend/assets/skill.js` → `backend/skills/static/skills/js/skill.js` (with edits below)
- `frontend/vendor/tailwind.min.css` → `backend/skills/static/skills/vendor/tailwind.min.css`
- `frontend/vendor/highlight.min.css` and `.min.js` → `backend/skills/static/skills/vendor/`
- **Drop**: `frontend/vendor/marked.min.js` (no longer used — server renders markdown)
- **Drop**: `frontend/config.js` (no split deploy; API base is always same-origin)
- **Move**: `frontend/dev/install-modal-ui-audit.js` → `backend/skills/static/skills/dev/install-modal-ui-audit.js` (so it remains paste-into-console-runnable on `/skills/<some-skill>/`)

Templates reference assets via `{% static 'skills/css/app.css' %}` etc.

### `backend/skills/static/skills/js/home.js`

- Keep `cardHtml(skill)` and the existing render path. The template paints the *initial* grid server-side (no fetch needed); JS does **not** run on page load. The first time the user types in the search, picks a category, or changes the sort, JS fetches `/api/skills` once, caches the response in `allSkills`, and replaces `#skill-grid` innerHTML with `cardHtml`-built cards. Subsequent filter/sort/search reuses the cached `allSkills` (current behavior).
- **Add for item #4**: `home.js` updates a `#result-count` element on every render with `Showing X of N`. Adds a `#search-clear` button that's `hidden` when the query is empty, calls `searchInput.value = ''` + re-render on click. (`aria-label="Search skills"` is set on the `<input>` directly in the template.)
- The home template emits the same skill data the server-rendered grid is built from in a `<script id="skills-data" type="application/json">{{ skills_json|safe }}</script>` block. `home.js` reads that on first user interaction *instead* of refetching `/api/skills` — saves the round-trip. The `/api/skills` endpoint is kept for the (now-unused-by-the-frontend) JSON consumers and for future use.

### `backend/skills/static/skills/js/skill.js`

- Delete `parseHash()`, the `hashchange` listener, and `apiBase()` indirection.
- Read `var skillName = document.body.dataset.skillName;` and `var version = document.body.dataset.version || null;` to drive API calls.
- Delete `renderSkill(skill)` — server template renders all the metadata. Skill detail JS now does only:
  - Wire install button onclick → `openInstallModal()`
  - Install modal flow (unchanged from today)
  - Wire install tabs (unchanged)
  - On `DOMContentLoaded`, fetch the file viewer payload from `/api/skills/<name>/files` if `body.dataset.version` is empty, or `/api/skills/<name>/versions/<version>/files` if it's set. Render code blocks into `#files-container` with highlight.js (existing `renderFiles` logic — unchanged)
  - Keyboard shortcuts (Esc → back, D → download) — **bug-fixed-or-not is a deliberate scope choice**; the migration preserves current Esc behavior. Item #1 (Escape modal collision) is *deferred*.

### `backend/skills/parser.py`

Add at top: `import markdown`. In `parse_skill_from_dir`, set `'contentHtml': markdown.markdown(post.content, extensions=['fenced_code', 'tables'])` next to `'content'`. One change, ~3 LOC.

### `backend/requirements.txt` and `backend/requirements-dev.txt`

Add `markdown==3.x` (pin to a major version). No other new deps.

### `frontend/` directory

Deleted in the final commit of the migration (after templates are confirmed working). `git rm -r frontend/`.

---

## Migration order (execution-friendly)

1. **Branch + scaffolding**: cut `feature/django-templates`. Add `TEMPLATES` to `settings.py`. Add `markdown` to requirements. Add empty `backend/skills/templates/skills/` and `backend/skills/static/skills/` directories.
2. **Parser change**: add `contentHtml` to `parse_skill_from_dir` + a unit test in `skills/tests/test_parser.py` asserting markdown renders.
3. **Move static assets**: `git mv` `frontend/assets/*` and `frontend/vendor/*` (minus `marked.min.js`) into the new app-level static tree. Run `collectstatic` to verify.
4. **Build `base.html`** and a placeholder `home.html` and `skill_detail.html`. Wire one new URL (`path('', views.home)`) and the new `home` view. Smoke-test: visit `/`, see the page render with data.
5. **Build the rest of `home.html`** with full skill grid + search controls. Update `home.js` to drop `cardHtml`-on-load logic and add the result-count + clear-button (item #4).
6. **Build `skill_detail.html`** with metadata + server-rendered markdown + install modal markup. Wire `path('skills/<str:name>/', views.skill_detail)`. Update `skill.js` to read `data-skill-name`, drop hash routing, keep install + file-viewer.
7. **Wire version routes**: `path('skills/<str:name>/v/<str:version>/', ...)`. Update version selector to navigate.
8. **Drop old routes and `frontend/`**: remove the `index.html`/`skill.html`/`re_path` block from `urls.py`. `git rm -r frontend/`. Remove `FRONTEND_DIR` from `settings.py` and `.env.development` / `.env.production` if referenced. Search the codebase for any remaining `frontend/` reference and clean up (`backend/start.sh`, `backend/ecosystem.config.cjs`, `Dockerfile`, `CLAUDE.md`).
9. **Update CLAUDE.md** to reflect the new layout: templates, static layout, no split deploy, no `config.js`.
10. **Run all tests**: `pytest` + Playwright `e2e/`.

Each step is independently committable and leaves the app in a runnable state.

---

## Critical files

- **New**: `backend/skills/templates/skills/{base,home,skill_detail,404}.html`
- **New**: `backend/skills/static/skills/...` (relocated from `frontend/`)
- **Modified**: `backend/skill_market/settings.py` (add `TEMPLATES`, drop `STATICFILES_DIRS=[FRONTEND_DIR]`)
- **Modified**: `backend/skills/urls.py` (new HTML routes; drop shell + static `re_path`)
- **Modified**: `backend/skills/views.py` (replace `_read_shell` with `render(...)` views; API views untouched)
- **Modified**: `backend/skills/parser.py` (+`contentHtml`)
- **Modified**: `backend/skills/static/skills/js/{home,skill}.js` (shrunk; fix items #3, #4 inline)
- **Modified**: `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/requirements_py3.10_plus.txt`, `backend/requirements_py3.12.txt`, `backend/requirements_py3.8_3.9.txt` (+ `markdown`)
- **Modified**: `CLAUDE.md` (architecture section; static layout section; "deployable on its own" caveat removed)
- **Deleted**: `frontend/` (entire directory, after step 7 verifies)

---

## Reused existing functions/utilities

- `skills.watcher.get_skills()` — already returns the live in-memory dict; views call it directly (no DB).
- `skills.parser.parse_skill`, `parse_skill_from_dir`, `_parse_version_dir` — reused for version detail rendering, no behavior change.
- `skills.classifier.get_categories(skills_dict)` — already produces the category list for the home template's filter pills.
- `skills.views._install_paths`, `_version_dir`, `_parse_version_dir` — reused as-is by the new HTML views.
- `skills.middleware.ApiCorsMiddleware` — short-circuits OPTIONS only on `/api/*`, untouched. With no split deploy this is technically unused but harmless; consider removing in a follow-up cleanup.
- `parse_skill_from_dir` already produces all template fields (`name`, `description`, `license`, `category`, `icon`, `fileCount`, `lastUpdated`, `content`, plus the new `contentHtml`).
- Existing CSS classes in `app.css` for `.skill-markdown h1/h2/...` already target the markdown-rendered HTML structure — no template-side class adjustments needed.
- `frontend/dev/install-modal-ui-audit.js` is a sunk-cost regression test — keep it runnable post-migration by relocating it to `backend/skills/static/skills/dev/`.

---

## Verification

End-to-end checks after each step that produces a runnable app, plus a final pass once the migration is complete.

### Functional smoke (run `./backend/start.sh`, follow `feedback_ui_verify_visually.md` — both themes)

1. **Home page** loads with cards visible in the initial HTML response (verify with `curl http://localhost:8888/ | grep '<article'` or DevTools "View Page Source" — cards must be in source, not injected by JS). Search, category filters, sort still work after JS hydrates.
2. **Skill detail** at `/skills/<some-skill>/` shows title, description, category, license, file count, install paths, full rendered markdown. **Right-click → View Source confirms markdown is rendered server-side** (`<h1>`, `<pre>`, etc., visible in raw HTML).
3. **Versioned skill detail** at `/skills/<versioned-skill>/v/<YYYYMMDD-...>/` shows the right version's content. Version dropdown navigates correctly. `original` route works.
4. **404**: `/skills/does-not-exist/` returns the 404 template.
5. **Install modal** opens, lists targets, performs install, shows success/error. Cookie missing → warning + disabled rows. (Behavior unchanged from today.)
6. **Download ZIP** still works from the detail page (link → `/api/skills/<name>/zip`).
7. **File viewer** renders all files under the skill's main markdown, syntax-highlighted, with truncation warning for >500KB files.
8. **Theme toggle** persists; pre-paint `.dark` class still applied via the inline `<script>` in `base.html` head (no FOUC).
9. **Item #3 verification**: throttle network to "Slow 3G" in DevTools, hard-reload `/` — first paint should show real cards (not blank, not a skeleton); error retry button appears if the watcher initial parse fails (rare). Detail page shows content immediately.
10. **Item #4 verification**: type a query — result count updates ("Showing 3 of 27"); a × clear button appears in the search input; clicking × clears + restores full grid; screen reader announces "Search skills" on focus (input has proper `<label>` or `aria-label`).

### Unit tests (`pytest`)

- New: `skills/tests/test_parser.py::test_content_html_renders_markdown` — `## Hello` in SKILL.md produces `<h2>Hello</h2>` in `contentHtml`.
- Update: `skills/tests/test_views.py` — replace assertions on the old shell views with assertions on the new `home`/`skill_detail` views (response is HTML, contains `<title>`, contains the skill name in rendered output).
- Existing API tests remain valid — API surface is unchanged.

### E2E (`pytest backend/e2e/`)

- Update Playwright tests that visit `/skill.html#<name>` to visit `/skills/<name>/` instead.
- Add a test asserting a skill name appears in the **initial** HTML response (no JS), to lock in the server-rendering contract.

### Install modal regression

- Run `frontend/dev/install-modal-ui-audit.js` (relocated path) in DevTools console on `/skills/<some-skill>/`. Must still return `{passed: 64+, failed: 0}`. Modal markup is preserved verbatim, so this should pass without changes.

### Pre-merge checklist

- [ ] `frontend/` directory deleted
- [ ] No remaining references to `FRONTEND_DIR` in code, configs, or `.env*` examples
- [ ] No remaining references to `config.js`
- [ ] CLAUDE.md updated (stack note, statics & frontend section, env-loading section's `FRONTEND_DIR` mention)
- [ ] README still consistent (or note staleness explicitly)
- [ ] `collectstatic` succeeds
- [ ] `pytest` green
- [ ] `pytest backend/e2e/` green
- [ ] Manual click-through both themes per `feedback_ui_verify_visually.md`

---

## Out of scope (deferred to other branches)

- UI/UX item #1 — Escape modal collision in `skill.js` keydown handler
- UI/UX item #2 — Modal focus management (focus-on-open, focus trap, focus-return-on-close)
- UI/UX item #5 — `aria-pressed` / `aria-selected` semantics, dark-mode contrast on `.category-pill.active` and `.install-tab.active`, `:focus-visible` styles globally
- HTMX, partial server-render, or eager file-content rendering (rejected in brainstorming)
- Removing `ApiCorsMiddleware` (still harmless; cleanup-sized work)
- Removing the JSON detail/version-detail API endpoints (`/api/skills/<name>`, `/api/skills/<name>/versions/<v>`) — vestigial after this migration but kept for compat; deprecate in a follow-up.

---

## Where this spec belongs after exit

Per the brainstorming skill, this design should also be saved to `docs/superpowers/specs/2026-05-05-django-templates-migration-design.md` and committed once we're out of plan mode. The plan-mode constraint blocks me from writing it there now — happy to copy this same content there as the first action after `ExitPlanMode` is approved, before any code changes.
