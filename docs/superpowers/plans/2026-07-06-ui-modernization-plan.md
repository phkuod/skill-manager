# UI/UX Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernize the skill-manager site's visual design (indigo/violet accent, compact hero, curated "Featured" shelf, category filter, PyPI-style version picker) and repair the pre-existing broken `e2e/test_ui.py` suite along the way, per `docs/superpowers/specs/2026-07-06-ui-modernization-design.md`.

**Architecture:** Small additive backend change (a `category` field derived from the existing icon-keyword table, plus a server-side `featured_skills` slice) feeds a re-skinned, lightly restructured home page and skill-detail page. All other pages inherit the new CSS variables automatically. No new dependencies, no database, no new endpoints.

**Tech Stack:** Django 5.x templates, vanilla JS (no framework), hand-written CSS (`app.css`) layered over a JIT-purged Tailwind vendor bundle, pytest-django for unit/view tests, Playwright for e2e.

## Global Constraints

- No new Tailwind utility classes — the vendor bundle is JIT-purged and frozen; new visual elements get explicit classes in `app.css` (see CLAUDE.md's documented trap).
- No external fonts/CDNs — keep the existing system-font stack (`--font-main`, `--font-display`).
- `APPEND_SLASH = False` — new/changed routes (none in this plan) must not end in `/` unless they already do.
- Card DOM structure must stay compatible with `home.js`'s existing selectors (`.skill-card`, `.quick-install-btn`, `.skill-card-targets`, `.inline-confirm-row[data-confirm-slot]`) since `decorateVisibleCards()` and the install/uninstall pill logic depend on them.
- `skill_detail.html`'s `skill.js` IIFE already defines `var skillName = document.body.dataset.skillName` — new version-popover JS lives inside that same closure and reuses `skillName`, it does not redeclare it.
- Every task's tests run via the project's existing frameworks only: `pytest` (from repo root, venv active) for Python/Django tests, Playwright (`pytest e2e/`) for browser tests. No new test framework.

---

### Task 1: Backend — category classification in `parser.py`

**Files:**
- Modify: `skills/parser.py:102-122` (rename `_get_default_icon` → `_classify`, return `(icon, category)`)
- Modify: `skills/parser.py:125-164` (`parse_skill_from_dir` — use `_classify`, add `'category'` to returned dict)
- Test: `skills/tests/test_parser.py`

**Interfaces:**
- Produces: `_classify(skill_name: str, meta: dict | None) -> tuple[str, str]` — icon, category. Category is one of `Design`, `Tools`, `Code`, `Content`, `Testing`, `AI/ML`, `Communication`, `Other`.
- Produces: `parse_skill_from_dir(...)` return dict gains key `'category': str`. Consumed by Task 2.

- [ ] **Step 1: Write the failing tests**

Add to `skills/tests/test_parser.py` (after `test_parse_icon`, ~line 105):

```python
_KNOWN_CATEGORIES = {
    'Design', 'Tools', 'Code', 'Content', 'Testing', 'AI/ML',
    'Communication', 'Other',
}


def test_parse_category(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'valid-skill'), 'valid-skill')
    assert skill['category'] in _KNOWN_CATEGORIES


def test_classify_keyword_mapping():
    from skills.parser import _classify
    icon, category = _classify('pdf-converter', {})
    assert category == 'Tools'
    assert icon == '🔧'


def test_classify_fallback_category():
    from skills.parser import _classify
    icon, category = _classify('completely-unmatched-xyz', {})
    assert category == 'Other'
    assert icon == '📦'


def test_classify_meta_icon_override_still_classifies():
    # An explicit SKILL.md `icon:` overrides the icon but category still
    # derives from the name — there's no category field in frontmatter.
    from skills.parser import _classify
    icon, category = _classify('pdf-converter', {'icon': '🚀'})
    assert icon == '🚀'
    assert category == 'Tools'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/tests/test_parser.py -k "category or classify" -v`
Expected: FAIL — `ImportError: cannot import name '_classify'` (or `KeyError: 'category'` once import is fixed manually to `_get_default_icon`).

- [ ] **Step 3: Implement `_classify`**

Replace `skills/parser.py:102-122` (the `_get_default_icon` function) with:

```python
def _classify(skill_name, meta):
    """Resolve (icon, category) for a skill from its name keywords.

    An explicit `icon:` in SKILL.md frontmatter overrides only the icon;
    category always derives from the name since frontmatter has no
    category field.
    """
    name_lower = skill_name.lower()
    mapping = (
        (('design', 'art', 'theme', 'css', 'style', 'canvas', 'factory'), '🎨', 'Design'),
        (('tool', 'util', 'convert', 'pdf', 'docx', 'xlsx', 'pptx', 'zip'), '🔧', 'Tools'),
        (('code', 'dev', 'build', 'script', 'api', 'mcp', 'skill'), '💻', 'Code'),
        (('content', 'doc', 'write', 'comms', 'brand', 'internal'), '📝', 'Content'),
        (('test', 'qa', 'check', 'verify'), '🧪', 'Testing'),
        (('ai', 'ml', 'chat', 'claude', 'bot', 'data', 'algorithm'), '🤖', 'AI/ML'),
        (('slack', 'comm', 'message', 'gif'), '💬', 'Communication'),
        (('git', 'repo', 'version'), '📦', 'Other'),
    )
    default_icon, category = '📦', 'Other'
    for keywords, emoji, cat in mapping:
        if any(k in name_lower for k in keywords):
            default_icon, category = emoji, cat
            break

    icon = (meta or {}).get('icon') or default_icon
    return icon, category
```

- [ ] **Step 4: Wire `_classify` into `parse_skill_from_dir`**

In `skills/parser.py`, inside `parse_skill_from_dir` (currently line 138 `icon = _get_default_icon(skill_name, meta)` and the return dict at lines 155-164), change:

```python
    meta = post.metadata
    icon, category = _classify(skill_name, meta)
```

and add `'category': category,` to the returned dict, right after `'icon': icon,`:

```python
    return {
        'name': meta.get('name') or skill_name,
        'description': meta.get('description') or '',
        'license': meta.get('license') or 'Unknown',
        'icon': icon,
        'category': category,
        'fileCount': _count_files(dir_path),
        'lastUpdated': _last_modified(dir_path),
        'content': post.content,
        'contentHtml': content_html,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest skills/tests/test_parser.py -v`
Expected: PASS (all existing tests plus the 4 new ones — `test_parse_icon` still passes since `_classify` is only referenced internally, the public `parse_skill`/`parse_skill_from_dir` contract is unchanged except for the additive `category` key).

- [ ] **Step 6: Commit**

```bash
git add skills/parser.py skills/tests/test_parser.py
git commit -m "feat(ui): derive skill category from existing icon keyword table"
```

---

### Task 2: Backend — expose `category` and compute `featured_skills`

**Files:**
- Modify: `skills/views.py:92-95` (`_LIST_FIELDS`)
- Modify: `skills/views.py:124-130` (`home` view)
- Test: `skills/tests/test_views.py`

**Interfaces:**
- Consumes: `category` key from Task 1's `parse_skill_from_dir`.
- Produces: `/api/skills` and the `#skills-data` JSON blob on the home page now include `category` per skill. `home.html` render context gains `featured_skills: list[dict]` (up to 4 skills, sorted by `lastUpdated` descending, empty list if catalog has ≤4 skills).

- [ ] **Step 1: Write the failing tests**

Add to `skills/tests/test_views.py` (after `test_list_required_fields`, ~line 94):

```python
_KNOWN_CATEGORIES = {
    'Design', 'Tools', 'Code', 'Content', 'Testing', 'AI/ML',
    'Communication', 'Other',
}


def test_list_includes_category_field(client, version_fixture):
    res = client.get('/api/skills')
    skill = res.json()['skills'][0]
    assert 'category' in skill
    assert skill['category'] in _KNOWN_CATEGORIES
```

Add near the HTML views section (after `test_home_contains_skill_name_in_initial_html`, ~line 460):

```python
def test_home_shows_featured_shelf_for_large_catalog(client, version_fixture):
    # Real skill_repo fixture has 17 skills (see test_parse_all_real_repo), well
    # above the 4-skill threshold, so the Featured shelf must render.
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'Featured' in body


def test_home_hides_featured_shelf_for_small_catalog(client, monkeypatch):
    import skills.views as views

    def _tiny_skill(name, updated):
        return {
            'name': name, 'icon': '📦', 'category': 'Other', 'description': '',
            'fileCount': 1, 'lastUpdated': updated, 'content': '',
            'currentVersion': None, 'versions': [],
        }

    tiny = {
        'a': _tiny_skill('a', '2026-01-01T00:00:00+00:00'),
        'b': _tiny_skill('b', '2026-01-02T00:00:00+00:00'),
    }
    monkeypatch.setattr(views, 'get_skills', lambda: tiny)
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'Featured' not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/tests/test_views.py -k "category or featured" -v`
Expected: FAIL — `category` missing from `/api/skills` response; `'Featured' in body` fails since `home.html` has no such text yet.

- [ ] **Step 3: Implement**

In `skills/views.py`, change `_LIST_FIELDS` (lines 92-95):

```python
_LIST_FIELDS = (
    'name', 'icon', 'category', 'description', 'fileCount', 'lastUpdated',
    'content', 'currentVersion', 'versions',
)
```

Change the `home` view (lines 124-130):

```python
@require_GET
def home(request):
    skills_dict = get_skills()
    skills = [_summary(s) for s in skills_dict.values()]
    featured_skills = sorted(
        skills, key=lambda s: s.get('lastUpdated') or '', reverse=True
    )[:4] if len(skills) > 4 else []
    return render(request, 'skills/home.html', {
        'skills': skills,
        'featured_skills': featured_skills,
    })
```

(Note: Task 4 adds the actual "Featured" heading text to `home.html`; this step alone won't make the new tests pass yet, but the `test_home_shows_featured_shelf_for_large_catalog`/`test_home_hides_featured_shelf_for_small_catalog` tests are written now and will start passing once Task 4 lands. Run only the `category` test to confirm progress at this step; leave the two featured-shelf tests marked as expected-fail-until-Task-4 by running them explicitly later.)

- [ ] **Step 4: Run the category test to verify it passes**

Run: `pytest skills/tests/test_views.py -k category -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/views.py skills/tests/test_views.py
git commit -m "feat(ui): expose category field and server-side featured_skills slice"
```

---

### Task 3: Design tokens — indigo/violet accent + compact hero/shelf foundation

**Files:**
- Modify: `skills/static/skills/css/app.css:1-20` (`:root` accent variables)
- Modify: `skills/static/skills/css/app.css:22-38` (`.dark` accent variables)
- Modify: `skills/static/skills/css/app.css:421-446` (`.hero-section`/`.hero-title`/`.hero-subtitle` → `.hero-kicker` + new `.shelf-heading`)

**Interfaces:**
- Produces: `--accent`/`--accent-hover` now indigo/violet in both themes (same variable names, same consumers — no other file changes needed for the recolor to propagate). Produces new classes `.hero-kicker` and `.shelf-heading` for Task 4 to use.

- [ ] **Step 1: Change light-mode accent**

In `skills/static/skills/css/app.css`, in the `:root` block (lines 9-10), change:

```css
  --accent: #4f46e5;
  --accent-hover: #4338ca;
```

(was `--accent: #2563eb; --accent-hover: #1d4ed8;`)

- [ ] **Step 2: Change dark-mode accent**

In the `.dark` block (lines 30-31), change:

```css
  --accent: #a78bfa;
  --accent-hover: #c4b5fd;
```

(was `--accent: #6366f1; --accent-hover: #818cf8;`)

- [ ] **Step 3: Replace the hero section rules**

Replace the existing block (lines 421-446):

```css
.hero-section {
  padding: 6rem 1.5rem;
  text-align: center;
}

.hero-title {
  font-family: var(--font-display);
  font-size: 3.75rem; /* Slightly larger to compensate for system font plainness */
  font-weight: 800;
  line-height: 1;
  margin-bottom: 1.25rem;
  letter-spacing: -0.04em; /* Tighter tracking for that premium "Display" look */
  color: var(--text-primary);
  text-wrap: balance; /* Ensures even distribution of words across lines */
}

.hero-subtitle {
  font-size: 1.25rem;
  font-weight: 400;
  line-height: 1.6;
  color: var(--text-secondary);
  max-width: 700px;
  margin: 0 auto;
  opacity: 0.8;
  text-wrap: balance; /* Prevents single words from being orphaned on a new line */
}
```

with:

```css
.hero-kicker {
  padding: 1.75rem 1.5rem 1.25rem;
  text-align: center;
}

.hero-kicker p {
  font-size: 1rem;
  font-weight: 400;
  line-height: 1.6;
  color: var(--text-secondary);
  max-width: 640px;
  margin: 0 auto;
  text-wrap: balance;
}

.shelf-heading {
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--text-primary);
  margin: 0 0 0.75rem;
}
```

- [ ] **Step 4: Verify no dangling references to removed classes**

Run: `grep -rn "hero-section\|hero-title\|hero-subtitle" skills/templates skills/static/skills/js`
Expected: the only hits are in `skills/templates/skills/home.html` (3 lines) — that's expected at this point since Task 4 hasn't updated `home.html` yet. If any hit shows up outside `home.html`, stop and investigate before proceeding.

- [ ] **Step 5: Commit**

```bash
git add skills/static/skills/css/app.css
git commit -m "feat(ui): shift accent palette to indigo/violet, compact hero foundation"
```

---

### Task 4: Home page — card partial, Featured shelf, category filter

**Files:**
- Create: `skills/templates/skills/_skill_card.html`
- Modify: `skills/templates/skills/home.html:47-93` (hero, Featured shelf, All-skills section, category select)
- Modify: `skills/static/skills/js/home.js` (category filter state, `cardHtml`, `render`, URL state)
- Modify: `skills/static/skills/css/app.css` (append `.category-badge`)
- Test: `skills/tests/test_views.py`

**Interfaces:**
- Consumes: `skill.category` (Task 1/2), `.hero-kicker`/`.shelf-heading` (Task 3).
- Produces: `#category-select` element, `.category-badge` class, `_skill_card.html` partial consumed by both the Featured shelf and the main grid.

- [ ] **Step 1: Write the failing tests**

Add to `skills/tests/test_views.py` (near the other home-page tests):

```python
def test_home_has_category_select(client, version_fixture):
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'id="category-select"' in body


def test_home_card_shows_category_badge(client, version_fixture):
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'category-badge' in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/tests/test_views.py -k "category_select or category_badge" -v`
Expected: FAIL — neither string present yet.

- [ ] **Step 3: Create the card partial**

Create `skills/templates/skills/_skill_card.html` (extracted verbatim from the current `home.html` card markup, plus the new category badge):

```html
<a href="/skills/{{ skill.name }}/"
   class="skill-card block rounded-xl border p-5 transition-all hover:shadow-lg relative"
   style="background-color:var(--bg-card);border-color:var(--border);text-decoration:none">
  <div class="flex items-center justify-between gap-2 mb-3">
    <div class="flex items-center gap-4 min-w-0">
      <div class="icon-wrapper shrink-0">
        <span>{{ skill.icon }}</span>
      </div>
      <span class="category-badge">{{ skill.category|default:"Other" }}</span>
      <div class="skill-card-targets flex flex-wrap gap-1.5 items-center min-w-0 empty:hidden ml-1" data-skill-targets="{{ skill.name }}"></div>
    </div>
    <div class="inline-flex items-center gap-1.5 shrink-0 z-10" onclick="event.preventDefault(); event.stopPropagation();">
      <button type="button" class="quick-install-btn px-2.5 py-1 text-xs font-semibold rounded-lg border cursor-pointer transition-all hover:scale-105 hidden" style="color:var(--accent);border-color:var(--accent);background-color:var(--bg-primary);" data-skill="{{ skill.name }}">Install</button>
    </div>
  </div>
  <h3 class="font-semibold mb-1 truncate" style="color:var(--text-primary)">{{ skill.name }}</h3>
  <p class="text-sm mb-3 line-clamp-2" style="color:var(--text-secondary)">{{ skill.description }}</p>
  <div class="inline-confirm-row hidden" data-confirm-slot="{{ skill.name }}"></div>
  <div class="pt-2 border-t flex items-center justify-between text-xs" style="color:var(--text-secondary);border-color:var(--border)">
    <span>{{ skill.fileCount }} file{{ skill.fileCount|pluralize }}</span>
    <span>{{ skill.lastUpdated|slice:":10" }}</span>
  </div>
</a>
```

- [ ] **Step 4: Rewrite the home page content block**

Replace `skills/templates/skills/home.html` lines 47-93 (from `{% block content %}`'s `<section class="hero-section">` through the closing `</main>`) with:

```html
<section class="hero-kicker">
  <p>Discover, share, and install AI-powered skills to supercharge your workflow</p>
</section>

{% if featured_skills %}
<section class="mb-8 px-6">
  <h2 class="shelf-heading">Featured</h2>
  <div class="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
    {% for skill in featured_skills %}
      {% include "skills/_skill_card.html" %}
    {% endfor %}
  </div>
</section>
{% endif %}

<section class="mb-6 px-6 flex flex-wrap items-center gap-3">
  <h2 class="shelf-heading" style="margin:0;">All skills</h2>
  <div class="ml-auto flex items-center gap-2">
    <span id="result-count" class="text-sm" style="color:var(--text-secondary)">Showing {{ skills|length }} of {{ skills|length }}</span>
    <label for="category-select" class="text-sm" style="color:var(--text-secondary)">Category:</label>
    <select id="category-select" class="text-sm rounded-lg border px-2 py-1"
      style="background-color:var(--bg-secondary);color:var(--text-primary);border-color:var(--border)">
      <option value="">All</option>
      <option value="Design">Design</option>
      <option value="Tools">Tools</option>
      <option value="Code">Code</option>
      <option value="Content">Content</option>
      <option value="Testing">Testing</option>
      <option value="AI/ML">AI/ML</option>
      <option value="Communication">Communication</option>
      <option value="Other">Other</option>
    </select>
    <label for="sort-select" class="text-sm" style="color:var(--text-secondary)">Sort:</label>
    <select id="sort-select" class="text-sm rounded-lg border px-2 py-1"
      style="background-color:var(--bg-secondary);color:var(--text-primary);border-color:var(--border)">
      <option value="lastUpdated">Last Updated</option>
      <option value="name">Name</option>
    </select>
  </div>
</section>

<main class="px-6 pb-10">
  <div id="skill-grid" class="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
    {% for skill in skills %}
      {% include "skills/_skill_card.html" %}
    {% endfor %}
  </div>
  <p id="no-results" class="hidden text-center py-12" style="color:var(--text-secondary)">No skills match your search.</p>
</main>
```

- [ ] **Step 5: Run the Django-level tests to verify they pass**

Run: `pytest skills/tests/test_views.py -k "category_select or category_badge or featured" -v`
Expected: PASS (5 tests: the 2 from this task plus the 2 featured-shelf tests written in Task 2, plus category field).

- [ ] **Step 6: Add category filtering to `home.js`**

In `skills/static/skills/js/home.js`, add a new module-level variable next to `currentSort` (~line 10):

```javascript
  var currentCategory = '';
```

Add the element reference next to `sortSelect` (~line 20):

```javascript
  var categorySelect = document.getElementById('category-select');
```

In `cardHtml(skill)` (~lines 50-86), add the badge markup right after the `icon-wrapper` div and before the `skill-card-targets` div, so JS-rendered cards match the server-rendered partial:

```javascript
      '<div class="flex items-center gap-4 min-w-0">' +
        '<div class="icon-wrapper shrink-0">' +
          '<span>' + escapeHtml(skill.icon) + '</span>' +
        '</div>' +
        '<span class="category-badge">' + escapeHtml(skill.category || 'Other') + '</span>' +
        '<div class="skill-card-targets flex flex-wrap gap-1.5 items-center min-w-0 empty:hidden ml-1" data-skill-targets="' + escapeHtml(skill.name) + '">' + targetsHtml + '</div>' +
      '</div>' +
```

(This replaces the existing 4-line block without the category-badge span — same surrounding lines, one new line inserted.)

In `render()` (~lines 95-114), change the filter predicate to also check category:

```javascript
  function render() {
    ensureSkillsLoaded();
    var q = currentSearch.toLowerCase();
    var visible = allSkills.filter(function (s) {
      if (currentCategory && s.category !== currentCategory) return false;
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
    writeUrlState();
  }
```

In `writeUrlState()` (~lines 116-127), add a `cat` param:

```javascript
  function writeUrlState() {
    var params = new URLSearchParams();
    if (currentSearch) params.set('q', currentSearch);
    if (currentSort && currentSort !== DEFAULT_SORT) params.set('sort', currentSort);
    if (currentCategory) params.set('cat', currentCategory);
    var qs = params.toString();
    var newUrl = qs
      ? window.location.pathname + '?' + qs
      : window.location.pathname;
    window.history.replaceState(null, '', newUrl);
  }
```

In `hydrateFromUrl()` (~lines 129-145), read it back:

```javascript
  function hydrateFromUrl() {
    var params = new URLSearchParams(window.location.search);
    var q = params.get('q') || '';
    var sort = params.get('sort');
    var cat = params.get('cat');
    var dirty = false;
    if (q) {
      currentSearch = q;
      if (searchInput) searchInput.value = q;
      dirty = true;
    }
    if (sort === 'name' || sort === 'lastUpdated') {
      currentSort = sort;
      if (sortSelect) sortSelect.value = sort;
      if (sort !== DEFAULT_SORT) dirty = true;
    }
    if (cat) {
      currentCategory = cat;
      if (categorySelect) categorySelect.value = cat;
      dirty = true;
    }
    if (dirty) render();
  }
```

Add the change listener next to the existing `sortSelect` listener (~line 168-173):

```javascript
  if (categorySelect) {
    categorySelect.addEventListener('change', function () {
      currentCategory = categorySelect.value;
      render();
    });
  }
```

- [ ] **Step 7: Add the category badge CSS**

Append to the end of `skills/static/skills/css/app.css`:

```css
/* ---------- Category badge (home page cards) ---------- */
.category-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  background-color: var(--bg-secondary);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  font-size: 0.7rem;
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
}
```

- [ ] **Step 8: Manual smoke check**

Run: `DEBUG=True SKILL_REPO_PATH=./skill_repo venv/Scripts/python.exe manage.py runserver 127.0.0.1:8899 --noreload` in the background, then in another shell: `curl -s http://127.0.0.1:8899/ | grep -o 'category-select\|category-badge\|Featured' | sort -u`
Expected output contains all three: `Featured`, `category-badge`, `category-select`. Stop the server afterward.

- [ ] **Step 9: Run full Python test suite to check for regressions**

Run: `pytest skills/tests/ -v`
Expected: PASS, no regressions in unrelated tests.

- [ ] **Step 10: Commit**

```bash
git add skills/templates/skills/_skill_card.html skills/templates/skills/home.html skills/static/skills/js/home.js skills/static/skills/css/app.css skills/tests/test_views.py
git commit -m "feat(ui): add Featured shelf and category filter to home page"
```

---

### Task 5: Skill detail page — version popover, license badge, dead-code removal

**Files:**
- Modify: `skills/templates/skills/skill_detail.html:39-50`
- Modify: `skills/static/skills/js/skill.js:1-29` (remove dead `copyCommand`)
- Modify: `skills/static/skills/js/skill.js:211-238` (remove dead install-tabs listener, replace version `<select>` handler with popover)
- Modify: `skills/static/skills/css/app.css` (remove `.version-badge`/`.version-select` rules, add `.version-popover*` and `.license-badge`)
- Test: `skills/tests/test_views.py`

**Interfaces:**
- Consumes: `skill.license`, `skill.versions`, `skill.currentVersion` (all pre-existing, unchanged).
- Produces: `#version-popover`, `#version-popover-trigger`, `#version-popover-list`, `.license-badge` — consumed only by this task's own JS/CSS and by Task 6's e2e test rewrites.

- [ ] **Step 1: Write the failing tests**

Add to `skills/tests/test_views.py`:

```python
def test_skill_detail_shows_license_badge(client, version_fixture):
    res = client.get('/skills/pdf/')
    body = res.content.decode('utf-8')
    assert 'license-badge' in body


def test_skill_detail_shows_version_popover(client, version_fixture):
    res = client.get('/skills/webapp-testing/')
    body = res.content.decode('utf-8')
    assert 'id="version-popover"' in body
    assert 'version-popover-item' in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/tests/test_views.py -k "license_badge or version_popover" -v`
Expected: FAIL — neither string present in current markup.

- [ ] **Step 3: Verify `pdf` skill has a license containing "Proprietary"**

Run: `grep -i license skill_repo/pdf/SKILL.md`
Expected: a line containing `Proprietary` (confirms the test assertion target is real data, not asserting nothing).

- [ ] **Step 4: Replace the version-select markup with a popover**

In `skills/templates/skills/skill_detail.html`, replace lines 39-50 (the `<div class="flex flex-wrap items-center gap-3 mb-1">...</div>` block through the closing `{% endif %}`/`</div>`, i.e. everything from the name/version-badge div through immediately before `<p style="color:var(--text-secondary)">{{ skill.description }}</p>`) with:

```html
        <div class="flex flex-wrap items-center gap-3 mb-1">
          <h1 class="text-2xl font-bold" style="color:var(--text-primary)">{{ skill.name }}</h1>
          <span class="license-badge" title="License">{{ skill.license }}</span>
          {% if skill.versions %}
          <div class="version-popover" id="version-popover">
            <button type="button" id="version-popover-trigger" class="version-popover-trigger" aria-haspopup="listbox" aria-expanded="false">
              v{{ version|default:skill.currentVersion }}
              <svg class="version-popover-caret" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
            </button>
            <ul id="version-popover-list" class="version-popover-list hidden" role="listbox">
              {% for v in skill.versions %}
                <li class="version-popover-item{% if v.version == version or not version and v.version == skill.currentVersion %} is-active{% endif %}" data-version="{{ v.version }}" role="option">
                  <span>v{{ v.version }}</span>
                  {% if v.version == skill.currentVersion %}<span class="version-popover-current-badge">current</span>{% endif %}
                </li>
              {% endfor %}
            </ul>
          </div>
          {% endif %}
        </div>
```

- [ ] **Step 5: Run the Django tests to verify they pass**

Run: `pytest skills/tests/test_views.py -k "license_badge or version_popover" -v`
Expected: PASS.

- [ ] **Step 6: Remove dead `copyCommand` function**

In `skills/static/skills/js/skill.js`, delete lines 3-29 (the `// Copy-to-clipboard...` comment block through the `copyCommand` function and its trailing blank line), leaving:

```javascript
'use strict';

(function () {
  var skillName = document.body.dataset.skillName || '';
```

(Verify first with `grep -rn "copyCommand" skills/templates/` that no template calls it — expected: no output.)

- [ ] **Step 7: Remove dead install-tabs listener, replace version-select handler**

In `skills/static/skills/js/skill.js`, replace the block currently at lines 211-238 (the "Install tabs" comment through the closing `}` of the version-select `if` block) with:

```javascript
  // -------------------------------------------------------------------------
  // Version popover (path navigation)
  // -------------------------------------------------------------------------

  var versionPopover = document.getElementById('version-popover');
  if (versionPopover) {
    var versionTrigger = document.getElementById('version-popover-trigger');
    var versionList = document.getElementById('version-popover-list');

    var closeVersionPopover = function () {
      versionList.classList.add('hidden');
      versionTrigger.setAttribute('aria-expanded', 'false');
    };

    versionTrigger.addEventListener('click', function (e) {
      e.stopPropagation();
      var isOpen = !versionList.classList.contains('hidden');
      if (isOpen) {
        closeVersionPopover();
      } else {
        versionList.classList.remove('hidden');
        versionTrigger.setAttribute('aria-expanded', 'true');
      }
    });

    versionList.addEventListener('click', function (e) {
      var item = e.target.closest('.version-popover-item');
      if (!item) return;
      var v = item.dataset.version;
      window.location.href = '/skills/' + encodeURIComponent(skillName) + '/v/' + encodeURIComponent(v) + '/';
    });

    document.addEventListener('click', function (e) {
      if (!versionPopover.contains(e.target)) closeVersionPopover();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeVersionPopover();
    });
  }
```

- [ ] **Step 8: Replace version-badge/version-select CSS with version-popover/license-badge CSS**

In `skills/static/skills/css/app.css`, remove the `.version-badge`, `.version-select`, `.version-select:hover`, `.version-badge::after`, `.version-badge:hover::after` rules (the block starting `/* Version selector badge */` through the rule ending `.version-badge:hover::after { ... }`), and append this in their place (or anywhere after the removed block):

```css
/* ---------- Version popover (skill detail) ---------- */
.version-popover {
  position: relative;
  display: inline-flex;
}

.version-popover-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background-color: var(--bg-secondary);
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s ease;
}
.version-popover-trigger:hover,
.version-popover-trigger[aria-expanded="true"] {
  border-color: var(--accent);
  color: var(--text-primary);
  background-color: var(--bg-primary);
}
.version-popover-caret {
  transition: transform 0.15s ease;
}
.version-popover-trigger[aria-expanded="true"] .version-popover-caret {
  transform: rotate(180deg);
}

.version-popover-list {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 20;
  min-width: 160px;
  max-height: 260px;
  overflow-y: auto;
  margin: 0;
  padding: 6px;
  list-style: none;
  border: 1px solid var(--border);
  border-radius: 10px;
  background-color: var(--bg-card);
  box-shadow: 0 12px 32px -8px rgba(0, 0, 0, 0.25);
}
.version-popover-list.hidden { display: none; }

.version-popover-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
  color: var(--text-primary);
  cursor: pointer;
  transition: background-color 0.12s ease;
}
.version-popover-item:hover {
  background-color: var(--bg-secondary);
}
.version-popover-item.is-active {
  background-color: var(--bg-secondary);
  font-weight: 700;
  color: var(--accent);
}
.version-popover-current-badge {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--result-ok-text);
  background-color: var(--result-ok-bg);
  padding: 1px 6px;
  border-radius: 999px;
}

.license-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  background-color: var(--bg-secondary);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  font-size: 0.7rem;
  font-weight: 600;
  white-space: nowrap;
}
```

- [ ] **Step 9: Run full Python test suite to check for regressions**

Run: `pytest skills/tests/ -v`
Expected: PASS, no regressions.

- [ ] **Step 10: Commit**

```bash
git add skills/templates/skills/skill_detail.html skills/static/skills/js/skill.js skills/static/skills/css/app.css skills/tests/test_views.py
git commit -m "feat(ui): PyPI-style version popover, license badge, remove dead install-tabs JS"
```

---

### Task 6: Repair `e2e/test_ui.py`

**Files:**
- Modify: `e2e/test_ui.py`

**Interfaces:**
- Consumes: `#content-section` (pre-existing, unhidden by `skill.js` after file-load — Task 5 didn't touch this), `#category-select` (Task 4), `#version-popover`/`.version-popover-item` (Task 5), `.license-badge` (Task 5), `#footer-count` (pre-existing, in `base.html`).

- [ ] **Step 1: Ensure e2e dependencies are installed**

Run: `venv/Scripts/python.exe -m pip show requests playwright 2>&1 | head -5` — if either is missing:
Run: `venv/Scripts/python.exe -m pip install requests playwright pytest-playwright && venv/Scripts/python.exe -m playwright install chromium`

- [ ] **Step 2: Fix `_open_detail` to wait on a real element**

In `e2e/test_ui.py`, change (lines 14-17):

```python
def _open_detail(page, server_url, name):
    """Navigate to the detail page and wait for it to finish loading."""
    page.goto(f"{server_url}/skills/{name}/")
    page.locator("#content-section").wait_for(state="visible", timeout=5000)
```

- [ ] **Step 3: Fix the stats test to match real copy**

Replace `test_home_shows_stats` (lines 30-34):

```python
def test_home_shows_stats(page, server_url):
    page.goto(server_url)
    assert page.locator("#footer-count").inner_text() == "17"
    assert "skills available" in page.inner_text("footer")
```

- [ ] **Step 4: Fix the category tests to use the dropdown, not pills**

Replace `test_home_has_category_pills` (lines 42-46):

```python
def test_home_has_category_select(page, server_url):
    page.goto(server_url)
    select = page.locator("#category-select")
    assert select.is_visible()
    assert select.locator("option").count() >= 2
```

Replace `test_category_filter_reduces_cards` (lines 96-111):

```python
def test_category_filter_reduces_cards(page, server_url):
    page.goto(server_url)
    options = page.locator("#category-select option")
    non_all_value = None
    for i in range(options.count()):
        val = options.nth(i).get_attribute("value")
        if val:
            non_all_value = val
            break
    assert non_all_value, "Expected at least one non-'All' category option"
    page.select_option("#category-select", non_all_value)
    page.wait_for_timeout(300)

    visible_count = sum(
        1 for i in range(page.locator(".skill-card").count())
        if page.locator(".skill-card").nth(i).is_visible()
    )
    assert 0 < visible_count < 17
```

Replace `test_all_category_pill_restores_all` (lines 114-133):

```python
def test_category_select_all_restores_all_cards(page, server_url):
    page.goto(server_url)
    options = page.locator("#category-select option")
    non_all_value = None
    for i in range(options.count()):
        val = options.nth(i).get_attribute("value")
        if val:
            non_all_value = val
            break
    page.select_option("#category-select", non_all_value)
    page.wait_for_timeout(200)
    page.select_option("#category-select", "")
    page.wait_for_timeout(200)

    visible_count = sum(
        1 for i in range(page.locator(".skill-card").count())
        if page.locator(".skill-card").nth(i).is_visible()
    )
    assert visible_count == 17
```

- [ ] **Step 5: Fix the license test (now passes unchanged — verify only)**

`test_detail_shows_license` (lines 197-199) needs no code change — it already asserts `"Proprietary" in page.inner_text("body")`, and Task 5 added the `.license-badge` element that renders `{{ skill.license }}`. No edit needed here; this step is a note, not a diff.

- [ ] **Step 6: Replace the install-paths test with an install-modal test**

Replace `test_detail_shows_install_paths` (lines 202-206):

```python
def test_detail_install_button_opens_modal(page, server_url):
    _open_detail(page, server_url, "pdf")
    page.locator("#install-button").click()
    page.wait_for_timeout(200)
    modal = page.locator("#install-modal")
    assert "is-open" in (modal.get_attribute("class") or "")
```

- [ ] **Step 7: Run the full e2e suite**

Run: `DEBUG=True venv/Scripts/python.exe -m pytest e2e/test_ui.py -v`
Expected: PASS — 19 tests (renamed but same count: `test_home_has_category_pills` → `test_home_has_category_select`, `test_all_category_pill_restores_all` → `test_category_select_all_restores_all_cards`, `test_detail_shows_install_paths` → `test_detail_install_button_opens_modal`).

- [ ] **Step 8: Commit**

```bash
git add e2e/test_ui.py
git commit -m "fix(e2e): repair test_ui.py for category-select, version-popover, and content-section markup"
```

---

### Task 7: Final verification pass

**Files:** none (verification only; fix forward in the relevant file from Tasks 1-6 if something fails)

- [ ] **Step 1: Run the full Python test suite**

Run: `pytest -v`
Expected: PASS, 0 failures.

- [ ] **Step 2: Re-run the install-modal UI audit**

Start the dev server (`./start.sh` or the manual runserver command from Task 4 Step 8), open `/skills/pdf/` (or any skill) in a browser, open DevTools console, paste the contents of `skills/static/skills/dev/install-modal-ui-audit.js`, and run it.
Expected: `{passed: 64+, failed: 0}` — the accent-color change (Task 3) and detail-page header changes (Task 5) touch the same markup this audit covers.

- [ ] **Step 3: Manual cross-page/theme/viewport check**

In a browser at ~1280px width, both light and dark theme (toggle via the theme button):
- Load `/` — confirm the Featured shelf appears (17-skill catalog, well above the 4-skill threshold), the category select narrows the grid, sort still works, console is clean.
- Load `/skills/webapp-testing/` — confirm the version popover opens/closes, clicking a version navigates to `/skills/webapp-testing/v/<version>/`, the license badge shows text, console is clean.
- Repeat both pages at ~375px width — confirm no horizontal overflow, header/search/nav still usable, category+sort selects don't overflow their row.

Expected: no visual regressions, no console errors, in either theme at either width.

- [ ] **Step 4: Run the e2e suite one final time**

Run: `DEBUG=True venv/Scripts/python.exe -m pytest e2e/test_ui.py -v`
Expected: PASS, 19/19.

No commit for this task — it's verification-only. If any step surfaces a bug, fix it in the owning file from Tasks 1-6 and commit with an appropriately scoped message (e.g. `fix(ui): ...`).
