# UI Refinement (Execution Polish) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Second-round visual polish per `docs/superpowers/specs/2026-07-08-ui-refinement-design.md`: focus-visible system, reduced-motion support, pill unification, markdown typography, home-card/toolbar cleanup, quiet detail-page panel headers, classed action buttons. No JS logic, backend, or route changes.

**Architecture:** All styling changes land in `skills/static/skills/css/app.css` as explicit classes (the vendored Tailwind bundle is JIT-purged and frozen). Markup edits are surgical: `_skill_card.html` + the mirrored `cardHtml()` template string in `home.js` (markup only), the home toolbar/kicker in `home.html`, and the detail-page header/action-row in `skill_detail.html`.

**Tech Stack:** Django 5.x templates, vanilla JS, hand-written CSS over frozen Tailwind vendor bundle, pytest-django, Playwright e2e.

## Global Constraints

- No new Tailwind utility classes — vendor bundle is JIT-purged/frozen; new visuals get explicit classes in `app.css`. Existing utility classes already present in markup (`flex`, `w-4 h-4`, `text-sm`, etc.) are safe to reuse.
- No web fonts, no CDNs, no new dependencies.
- No JS *logic* changes — `home.js` edits are confined to the HTML template string in `cardHtml()`.
- Selector contract must survive verbatim: `.skill-card`, `.quick-install-btn`, `.skill-card-targets`, `.inline-confirm-row[data-confirm-slot]`, `#category-select`, `#sort-select`, `#result-count` (text format `Showing X of Y`), `#skill-grid`, `#no-results`, `#files-section`, `#content-section`, `#file-count-badge`, `#content-panel-title`, `#file-explorer-container`, `#file-explorer-chevron`, `#install-button`, `#download-link`, `#version-popover*`, `.license-badge`, `.category-badge`, all `install-modal-*` IDs/classes, footer classes `pt-2 border-t` on the card meta row (home.js `decorateVisibleCards()` locates the footer via `.pt-2.border-t`).
- Tests: `pytest skills/tests/` (venv active, repo root) and `pytest e2e/` (Playwright, port 8799). Test fixtures are `(client, version_fixture)` — `version_fixture` is module-scoped autouse in `skills/tests/test_views.py`.
- Commit format `<type>: <description>`; one commit per task.

---

### Task 1: Shared CSS polish (`app.css` only)

**Files:**
- Modify: `skills/static/skills/css/app.css`

**Interfaces:**
- Produces: `:focus-visible` outline system, `prefers-reduced-motion` block, unified pill metrics. No new class names consumed by templates in this task. Later tasks append their own classes; this task must not rename any existing class.

- [ ] **Step 1: Merge the duplicated `body` rules**

`app.css` declares `body {}` twice. Replace the first rule (lines 40-46):

```css
body {
  font-family: var(--font-main);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  transition: background-color 0.3s cubic-bezier(0.4, 0, 0.2, 1), color 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  -webkit-font-smoothing: antialiased;
}
```

with the merged rule:

```css
body {
  font-family: var(--font-main);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.01em; /* Subtle modern touch for system fonts */
  transition: background-color 0.3s cubic-bezier(0.4, 0, 0.2, 1), color 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  -webkit-font-smoothing: antialiased;
}
```

and delete the second `body` rule entirely (currently lines 459-466):

```css
body {
  font-family: var(--font-main);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  margin: 0;
  -webkit-font-smoothing: antialiased;
  letter-spacing: -0.01em; /* Subtle modern touch for system fonts */
}
```

- [ ] **Step 2: Remove the dead `.install-tab` rules**

Delete this block (currently lines 123-135 — its markup was removed in commit `fde7741`; verify first with `grep -rn "install-tab" skills/templates skills/static/skills/js` → expected no hits):

```css
/* Install tabs */
.install-tab {
  background-color: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: background-color 0.15s, color 0.15s;
}
.install-tab.active {
  background-color: var(--accent);
  color: #ffffff;
  border-color: var(--accent);
}
```

- [ ] **Step 3: Add the focus-visible system**

Append to the end of `app.css`:

```css
/* ===========================================================================
 * Refinement pass (2026-07-08): focus-visible system, reduced motion.
 * =========================================================================== */

/* Consistent keyboard-focus ring. :focus-visible only — no ring on mouse
 * click. #search-input is excluded: it keeps its own focus:ring-2 utility
 * and would double-ring otherwise. */
a:focus-visible,
button:focus-visible,
select:focus-visible,
input:focus-visible:not(#search-input),
[role="option"]:focus-visible,
[tabindex]:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
  }
  .skill-card:hover,
  .skill-card:hover .icon-wrapper {
    transform: none;
  }
}
```

- [ ] **Step 4: Unify pill metrics**

(a) Replace the existing `.license-badge` rule (currently lines 302-313):

```css
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

with a grouped rule covering all pill-family members:

```css
/* Shared pill family — one metric set for all small status chips. */
.license-badge,
.category-badge,
.installed-target-type,
.installed-card-badge {
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

(b) Delete the now-redundant standalone `.category-badge` block at the end of the file, replacing it with only its non-shared declaration:

```css
/* ---------- Category badge (home page cards) ---------- */
.category-badge {
  flex-shrink: 0;
}
```

(c) Replace `.installed-target-type` (currently lines 796-802):

```css
.installed-target-type {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--text-secondary);
}
```

with nothing (delete it — the grouped rule covers it; grouped rule appears earlier in the file than the installed-page section, and there is no other `.installed-target-type` rule, so no cascade conflict).

(d) Replace `.installed-card-badge` (currently lines 850-857):

```css
.installed-card-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 6px;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  margin-left: 8px;
}
```

with only its non-shared declaration:

```css
.installed-card-badge {
  margin-left: 8px;
}
```

(e) In `.version-popover-trigger` (currently lines 225-239), change `padding: 4px 12px;` → `padding: 3px 12px;` and `font-size: 0.75rem;` → `font-size: 0.7rem;` so the trigger reads as the same pill family while keeping its button affordance (gap, caret, hover states unchanged).

- [ ] **Step 5: Markdown typography refinements**

In the `.skill-markdown` block (currently lines 138-194), change exactly these declarations:

- `.skill-markdown h1`: `font-size: 1.5rem` → `font-size: 1.6rem`
- `.skill-markdown h2`: `font-size: 1.25rem` → `font-size: 1.3rem`, and append to the same rule: `padding-bottom: 0.3rem; border-bottom: 1px solid var(--border);`
- `.skill-markdown p`: `line-height: 1.6` → `line-height: 1.65`
- `.skill-markdown pre`: `padding: 1rem` → `padding: 1rem 1.25rem`, `border-radius: 8px` → `border-radius: 10px`
- `.skill-markdown th`: append `border-bottom: 2px solid var(--border);`

Resulting rules (full text for verification):

```css
.skill-markdown h1 { font-size: 1.6rem; font-weight: 700; margin: 1.5rem 0 0.75rem; color: var(--text-primary); }
.skill-markdown h2 { font-size: 1.3rem; font-weight: 600; margin: 1.25rem 0 0.5rem; color: var(--text-primary); padding-bottom: 0.3rem; border-bottom: 1px solid var(--border); }
.skill-markdown p { margin: 0.5rem 0; line-height: 1.65; color: var(--text-primary); }
.skill-markdown pre {
  margin: 0.75rem 0;
  padding: 1rem 1.25rem;
  border-radius: 10px;
  overflow-x: auto;
  background-color: var(--bg-secondary) !important;
  border: 1px solid var(--border);
}
.skill-markdown th {
  font-weight: 600;
  background-color: var(--bg-secondary);
  border-bottom: 2px solid var(--border);
}
```

(h3/h4/ul/ol/li/code/table/td/a/blockquote/strong/hr rules unchanged.)

- [ ] **Step 6: Verify nothing broke**

Run: `grep -c "^body {" skills/static/skills/css/app.css`
Expected: `1`

Run: `grep -n "install-tab" skills/static/skills/css/app.css skills/templates -r`
Expected: no output.

Run: `pytest skills/tests/ -q`
Expected: PASS (CSS-only change; suite must stay green).

- [ ] **Step 7: Commit**

```bash
git add skills/static/skills/css/app.css
git commit -m "feat(ui): focus-visible system, reduced motion, pill unification, markdown typography"
```

---

### Task 2: Card layout — category badge to footer row

**Files:**
- Modify: `skills/templates/skills/_skill_card.html`
- Modify: `skills/static/skills/js/home.js:52-92` (`cardHtml()` template string only)
- Modify: `skills/static/skills/css/app.css` (append `.skill-card .icon-wrapper` fix)
- Test: `skills/tests/test_views.py`

**Interfaces:**
- Consumes: pill family metrics from Task 1 (`.category-badge` shared rule).
- Produces: card footer row structure `<div class="pt-2 border-t ..."><span class="category-badge">…</span><span>…files · date</span></div>`. Selectors `.skill-card`, `.quick-install-btn`, `.skill-card-targets`, `.inline-confirm-row[data-confirm-slot]`, footer `pt-2 border-t` all preserved.

- [ ] **Step 1: Write the failing test**

Add to `skills/tests/test_views.py`, immediately after `test_home_card_shows_category_badge` (the existing test at ~line 514):

```python
def test_home_card_category_badge_in_footer(client, version_fixture):
    # Refined card layout: the category badge lives in the footer meta row,
    # which renders *after* the inline-confirm slot in card markup. In the
    # old layout the badge sat in the top row (before the slot).
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'data-confirm-slot' in body and 'category-badge' in body
    assert body.index('data-confirm-slot') < body.index('category-badge')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/tests/test_views.py::test_home_card_category_badge_in_footer -v`
Expected: FAIL on the ordering assertion (badge currently renders in the top row, before the confirm slot).

- [ ] **Step 3: Rewrite the card partial**

Replace the full contents of `skills/templates/skills/_skill_card.html` with:

```html
<a href="/skills/{{ skill.name }}/"
   class="skill-card block rounded-xl border p-5 transition-all hover:shadow-lg relative"
   style="background-color:var(--bg-card);border-color:var(--border);text-decoration:none">
  <div class="flex items-center justify-between gap-2 mb-3">
    <div class="flex items-center gap-3 min-w-0">
      <div class="icon-wrapper shrink-0">
        <span>{{ skill.icon }}</span>
      </div>
      <div class="skill-card-targets flex flex-wrap gap-1.5 items-center min-w-0 empty:hidden" data-skill-targets="{{ skill.name }}"></div>
    </div>
    {# preventDefault (not stopPropagation): keeps the wrapping <a> from navigating on a click here, while letting a click on the actual button/pill bubble up to the document-level delegated handler in home.js. #}
    <div class="inline-flex items-center gap-1.5 shrink-0 z-10" onclick="event.preventDefault();">
      <button type="button" class="quick-install-btn px-2.5 py-1 text-xs font-semibold rounded-lg border cursor-pointer transition-all hover:scale-105 hidden" style="color:var(--accent);border-color:var(--accent);background-color:var(--bg-primary);" data-skill="{{ skill.name }}">Install</button>
    </div>
  </div>
  <h3 class="font-semibold mb-1 truncate" style="color:var(--text-primary)">{{ skill.name }}</h3>
  <p class="text-sm mb-3 line-clamp-2" style="color:var(--text-secondary)">{{ skill.description }}</p>
  <div class="inline-confirm-row hidden" data-confirm-slot="{{ skill.name }}"></div>
  <div class="pt-2 border-t flex items-center justify-between text-xs" style="color:var(--text-secondary);border-color:var(--border)">
    <span class="category-badge">{{ skill.category|default:"Other" }}</span>
    <span>{{ skill.fileCount }} file{{ skill.fileCount|pluralize }} · {{ skill.lastUpdated|slice:":10" }}</span>
  </div>
</a>
```

(Changes: category badge moved from top row to footer-left; footer-right merges file count + date into one span with a `·` separator; top-row gap `gap-4` → `gap-3` and the `ml-1` on `.skill-card-targets` dropped — the badge that justified them is gone.)

- [ ] **Step 4: Mirror the same structure in `home.js::cardHtml()`**

In `skills/static/skills/js/home.js`, replace the `return (...)` template of `cardHtml` (currently lines 64-91) with:

```javascript
    return (
      '<a href="/skills/' + encodeURIComponent(skill.name) + '/"' +
      ' class="skill-card block rounded-xl border p-5 transition-all hover:shadow-lg relative"' +
      ' style="background-color:var(--bg-card);border-color:var(--border);text-decoration:none">' +
        '<div class="flex items-center justify-between gap-2 mb-3">' +
          '<div class="flex items-center gap-3 min-w-0">' +
            '<div class="icon-wrapper shrink-0">' +
              '<span>' + escapeHtml(skill.icon) + '</span>' +
            '</div>' +
            '<div class="skill-card-targets flex flex-wrap gap-1.5 items-center min-w-0 empty:hidden" data-skill-targets="' + escapeHtml(skill.name) + '">' + targetsHtml + '</div>' +
          '</div>' +
          // preventDefault (not stopPropagation) so the wrapping <a> doesn't
          // navigate on a click here, but a click on the actual button/pill
          // still bubbles up to the document-level delegated handler below.
          '<div class="inline-flex items-center gap-1.5 shrink-0 z-10" onclick="event.preventDefault();">' +
            installHtml +
          '</div>' +
        '</div>' +
        '<h3 class="font-semibold mb-1 truncate" style="color:var(--text-primary)">' + highlight(skill.name, q) + '</h3>' +
        '<p class="text-sm mb-3 line-clamp-2" style="color:var(--text-secondary)">' + highlight(skill.description, q) + '</p>' +
        '<div class="inline-confirm-row hidden" data-confirm-slot="' + escapeHtml(skill.name) + '"></div>' +
        '<div class="pt-2 border-t flex items-center justify-between text-xs" style="color:var(--text-secondary);border-color:var(--border)">' +
          '<span class="category-badge">' + escapeHtml(skill.category || 'Other') + '</span>' +
          '<span>' + skill.fileCount + ' file' + (skill.fileCount === 1 ? '' : 's') + ' · ' + escapeHtml(relativeTime(updated) || updated.slice(0, 10)) + '</span>' +
        '</div>' +
      '</a>'
    );
```

(Everything before the `return` — `q`, `updated`, `tgts`, `targetsHtml`, `installHtml` — is unchanged.)

- [ ] **Step 5: Neutralize the icon-wrapper margin in card context**

Append to `skills/static/skills/css/app.css`:

```css
/* Inside a card's flex top row the wrapper's bottom margin (a leftover from
 * the pre-flex layout) skews vertical centering. The detail page's 80px
 * icon usage keeps the default margin. */
.skill-card .icon-wrapper {
  margin-bottom: 0;
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest skills/tests/test_views.py -k "category" -v`
Expected: PASS — including the new footer-ordering test and the pre-existing `test_home_card_shows_category_badge`.

- [ ] **Step 7: Commit**

```bash
git add skills/templates/skills/_skill_card.html skills/static/skills/js/home.js skills/static/skills/css/app.css skills/tests/test_views.py
git commit -m "feat(ui): move card category badge to footer meta row, align top row"
```

---

### Task 3: Home toolbar + hero kicker

**Files:**
- Modify: `skills/templates/skills/home.html:48-87` (kicker section + toolbar section)
- Modify: `skills/static/skills/css/app.css` (kicker paddings; append `.shelf-heading-count`, `.toolbar-select`)
- Test: `skills/tests/test_views.py`

**Interfaces:**
- Consumes: `.shelf-heading` (existing), focus-visible system (Task 1).
- Produces: `.toolbar-select` class on both selects, `aria-label="Filter by category"` / `aria-label="Sort skills"`. IDs `#category-select`, `#sort-select`, `#result-count` and the `Showing X of Y` text format unchanged (consumed by `home.js` and `e2e/test_ui.py`).

- [ ] **Step 1: Write the failing tests**

Add to `skills/tests/test_views.py` after `test_home_has_category_select`:

```python
def test_home_selects_have_aria_labels(client, version_fixture):
    # Visible "Category:" / "Sort:" labels were replaced by aria-labels in
    # the refined toolbar.
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'aria-label="Filter by category"' in body
    assert 'aria-label="Sort skills"' in body
    assert 'for="category-select"' not in body
    assert 'for="sort-select"' not in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/tests/test_views.py::test_home_selects_have_aria_labels -v`
Expected: FAIL — aria-labels not present; `for="category-select"` still present.

- [ ] **Step 3: Replace the toolbar section in `home.html`**

Replace lines 63-87 (the `<section class="mb-6 px-6 flex flex-wrap items-center gap-3">` block) with:

```html
<section class="mb-6 px-6 flex flex-wrap items-center gap-3">
  <h2 class="shelf-heading" style="margin:0;">All skills <span class="shelf-heading-count">· {{ skills|length }}</span></h2>
  <div class="ml-auto flex flex-wrap items-center gap-2">
    <span id="result-count" class="text-sm" style="color:var(--text-secondary)">Showing {{ skills|length }} of {{ skills|length }}</span>
    <select id="category-select" class="toolbar-select" aria-label="Filter by category">
      <option value="">All categories</option>
      <option value="Design">Design</option>
      <option value="Tools">Tools</option>
      <option value="Code">Code</option>
      <option value="Content">Content</option>
      <option value="Testing">Testing</option>
      <option value="AI/ML">AI/ML</option>
      <option value="Communication">Communication</option>
      <option value="Other">Other</option>
    </select>
    <select id="sort-select" class="toolbar-select" aria-label="Sort skills">
      <option value="lastUpdated">Last Updated</option>
      <option value="name">Name</option>
    </select>
  </div>
</section>
```

(Note: the "All" option label becomes "All categories" for standalone clarity — its `value=""` is unchanged, which is what `home.js` and `e2e/test_ui.py::test_category_select_all_restores_all_cards` key on.)

- [ ] **Step 4: Tighten the hero kicker**

In `skills/static/skills/css/app.css`, change `.hero-kicker` (currently `padding: 1.75rem 1.5rem 1.25rem;`) and `.hero-kicker p` (currently `font-size: 1rem;`):

```css
.hero-kicker {
  padding: 0.9rem 1.5rem 0.6rem;
  text-align: center;
}

.hero-kicker p {
  font-size: 0.95rem;
  font-weight: 400;
  line-height: 1.6;
  color: var(--text-secondary);
  max-width: 640px;
  margin: 0 auto;
  text-wrap: balance;
}
```

- [ ] **Step 5: Add the toolbar CSS**

Append to `skills/static/skills/css/app.css`:

```css
/* ---------- Home toolbar ---------- */
.shelf-heading-count {
  color: var(--text-secondary);
  font-weight: 500;
}

.toolbar-select {
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background-color: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 0.85rem;
  font-family: inherit;
  cursor: pointer;
  transition: border-color 0.15s ease;
}
.toolbar-select:hover {
  border-color: var(--accent);
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest skills/tests/test_views.py -k "aria or category_select or featured" -v`
Expected: PASS — new aria test plus pre-existing `test_home_has_category_select` / featured-shelf tests.

- [ ] **Step 7: Commit**

```bash
git add skills/templates/skills/home.html skills/static/skills/css/app.css skills/tests/test_views.py
git commit -m "feat(ui): cleaner home toolbar with aria-labeled selects, tighter hero kicker"
```

---

### Task 4: Detail page — quiet panel headers, classed action buttons, hero rhythm

**Files:**
- Modify: `skills/templates/skills/skill_detail.html:32-135` (hero block, action row, panel headers)
- Modify: `skills/static/skills/css/app.css` (append `.panel-header*`, `.panel-chip`, `.detail-actions`, `.btn-accent`, `.btn-outline`)
- Test: `skills/tests/test_views.py`

**Interfaces:**
- Consumes: focus-visible system (Task 1).
- Produces: `.panel-header`, `.panel-header-title`, `.panel-chip`, `.detail-actions`, `.btn-accent`, `.btn-outline`. IDs `#files-section`, `#content-section`, `#file-count-badge`, `#content-panel-title`, `#file-explorer-container`, `#file-explorer-chevron`, `#install-button`, `#download-link` and `toggleFileExplorer()` wiring unchanged (consumed by `skill.js` and `e2e/test_ui.py`).

- [ ] **Step 1: Write the failing tests**

Add to `skills/tests/test_views.py` after `test_skill_detail_shows_version_popover`:

```python
def test_skill_detail_quiet_panel_headers(client, version_fixture):
    # Traffic-light window dots were replaced by quiet panel headers.
    res = client.get('/skills/pdf/')
    body = res.content.decode('utf-8')
    assert 'bg-red-500' not in body
    assert 'panel-header' in body


def test_skill_detail_classed_action_buttons(client, version_fixture):
    res = client.get('/skills/pdf/')
    body = res.content.decode('utf-8')
    assert 'btn-accent' in body
    assert 'btn-outline' in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/tests/test_views.py -k "quiet_panel or classed_action" -v`
Expected: FAIL — `bg-red-500` present; `panel-header`/`btn-accent`/`btn-outline` absent.

- [ ] **Step 3: Restyle the hero block and action row**

In `skills/templates/skills/skill_detail.html`, change the description paragraph (line 59) from:

```html
        <p style="color:var(--text-secondary)">{{ skill.description }}</p>
```

to:

```html
        <p style="color:var(--text-secondary);max-width:65ch">{{ skill.description }}</p>
```

Then replace the action row (lines 66-83, the `<div style="display: flex; gap: 0.75rem; margin-top: 1.5rem;">` block) with:

```html
    <div class="detail-actions">
      <button id="install-button" class="btn-accent" type="button" title="Install to target">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v12m0 0l-4-4m4 4l4-4M4 20h16"/></svg>
        Install
      </button>

      <a id="download-link"
        href="{% if version %}/api/skills/{{ skill_name }}/versions/{{ version }}/zip{% else %}/api/skills/{{ skill_name }}/zip{% endif %}"
        download="{{ skill_name }}.zip"
        title="Download ZIP (D)"
        class="btn-outline">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
        Download ZIP
      </a>
    </div>
```

- [ ] **Step 4: Replace the two panel headers**

Replace the files-section header (lines 94-104, the `<div class="px-4 py-3 border-b ...">` block containing the three dot divs and "File Explorer") with:

```html
          <div class="panel-header">
            <div class="panel-header-title">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>
              <span>Files</span>
            </div>
            <span id="file-count-badge"></span>
          </div>
```

Replace the content-section header (lines 115-125, the second traffic-light block containing `#content-panel-title` and "readonly") with:

```html
          <div class="panel-header">
            <div class="panel-header-title">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
              <span id="content-panel-title"></span>
            </div>
            <span class="panel-chip">readonly</span>
          </div>
```

- [ ] **Step 5: Add the new CSS classes**

Append to `skills/static/skills/css/app.css`:

```css
/* ---------- Detail page: quiet panel headers ---------- */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8rem;
  color: var(--text-secondary);
}
.panel-header-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.panel-header-title svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  opacity: 0.8;
}
.panel-chip {
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 1px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--text-secondary);
}

/* ---------- Detail page: action buttons ---------- */
.detail-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1.5rem;
}
.btn-accent,
.btn-outline {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0.5rem 1.25rem;
  border-radius: 10px;
  font-size: 0.875rem;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  text-decoration: none;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.1s ease;
}
.btn-accent {
  background-color: var(--accent);
  border: 1px solid var(--accent);
  color: #ffffff;
}
.btn-accent:hover {
  background-color: var(--accent-hover);
  border-color: var(--accent-hover);
}
.btn-accent:active {
  transform: translateY(1px);
}
/* Dark-mode accent is violet-400 — dark text reads far better on it than
 * white (contrast ~2.2:1 vs ~7:1). */
.dark .btn-accent {
  color: #0f172a;
}
.btn-outline {
  background-color: transparent;
  border: 1px solid var(--border);
  color: var(--text-primary);
}
.btn-outline:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.btn-outline:active {
  transform: translateY(1px);
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest skills/tests/test_views.py -k "quiet_panel or classed_action or license_badge or version_popover" -v`
Expected: PASS — the two new tests plus the pre-existing detail-page tests.

- [ ] **Step 7: Run the full unit suite**

Run: `pytest skills/tests/ -q`
Expected: PASS, no regressions.

- [ ] **Step 8: Commit**

```bash
git add skills/templates/skills/skill_detail.html skills/static/skills/css/app.css skills/tests/test_views.py
git commit -m "feat(ui): quiet detail-page panel headers, classed action buttons, hero rhythm"
```

---

### Task 5: Full verification pass

**Files:** none (verification only; fix forward in the owning file from Tasks 1-4 if something fails)

- [ ] **Step 1: Full Python suite**

Run: `pytest skills/tests/ -v`
Expected: PASS, 0 failures.

- [ ] **Step 2: e2e suite**

Run: `DEBUG=True venv/Scripts/python.exe -m pytest e2e/test_ui.py -v` (Bash; from repo root)
Expected: PASS 19/19 — the selector contract was preserved by design; any failure here means a selector regressed in Tasks 2-4, fix forward.

- [ ] **Step 3: Install-modal UI audit**

Start the dev server, open `/skills/pdf/` in a browser, paste `skills/static/skills/dev/install-modal-ui-audit.js` into the DevTools console, run.
Expected: `{passed: 64+, failed: 0}` — shared CSS (body merge, focus rules) could shift modal rendering.

- [ ] **Step 4: Visual pass (house rule — real browser, both themes, both widths)**

At ~1280px and ~375px, light and dark theme:
- `/` — card top row vertically centered (no badge crowding), badge in footer row, toolbar reads `All skills · N` left with tidy selects right, kicker compact, Featured shelf intact, console clean.
- `/skills/pdf/` (or any skill) — quiet panel headers (no traffic lights), Install/Download buttons with hover + active states, description wraps at a readable measure, console clean.
- Dark mode specifically: `.btn-accent` shows dark text on violet.

- [ ] **Step 5: Keyboard + reduced-motion pass**

- Tab through: header nav → search → toolbar selects → cards → (detail) Install/Download → version popover. Every stop shows the accent focus ring; no double ring on the search input.
- DevTools → emulate `prefers-reduced-motion: reduce` → card hover no longer lifts, install modal appears without scale animation.

No commit for this task — verification only.
