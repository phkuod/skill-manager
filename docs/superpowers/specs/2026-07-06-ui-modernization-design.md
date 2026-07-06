# UI/UX Modernization — Design System Refresh

**Date:** 2026-07-06
**Status:** Approved for planning

## Goal

Upgrade the visual design of the entire site to read as modern and
professional, informed by research into real-world "install a package
from a catalog" marketplace UIs (VS Code Marketplace, GitHub
Marketplace, Claude Plugins directory, Hugging Face Hub, PyPI). This is
a **visual and light-structural** refresh — no new subsystems, no
change to the no-database architecture, no new external dependencies
(fonts, JS libraries, CDNs).

## Research summary (grounds the decisions below)

- **VS Code Marketplace**: plain header, no gradient hero, install
  count + rating as trust signals, tabbed detail page.
- **GitHub Marketplace**: decorative-but-restrained hero with search
  directly below it, curated "shelves" (Featured / Recently added)
  instead of one giant grid.
- **Claude Plugins directory**: minimal hero, verified badge + install
  count + category tags on cards, sidebar filters with explicit
  Apply/Reset (not live-filter jank).
- **Hugging Face Hub**: dense filter rail and high card density — but
  only legible because of rigid column alignment; a pitfall for a
  smaller catalog like this one.
- **PyPI**: flat, reverse-chronological release list with the current
  version visually pinned, instead of a `<select>` dropdown.

Chosen direction: **"Curated Developer Marketplace"** — a blend of
GitHub Marketplace's shelf-based grouping and Claude Plugins'
restraint, with PyPI's version-list pattern applied to this app's
existing version picker.

## Scope

Full site design system (`base.html`, `app.css`) plus structural
changes to the home page and skill-detail page. All other pages
(`installed`, `contribute`, `usage`, `admin_contributions`,
`contribution_detail`, `my_contributions`) get re-skinned via the
shared CSS variables only — no layout changes this round.

## 1. Design tokens (`app.css`)

- **Accent color**: shift from blue to indigo/violet.
  - Light mode `--accent`: `#4f46e5` (indigo-600), `--accent-hover:
    #4338ca`.
  - Dark mode `--accent`: `#a78bfa` (violet-400), `--accent-hover:
    #c4b5fd`.
  - All other CSS variables (`--bg-*`, `--text-*`, `--border`,
    `--result-*`, `--highlight-*`) unchanged.
- **Typography**: keep the existing system-font stack (`--font-main`,
  `--font-display` — `Segoe UI Variable`/system-ui). No web fonts, per
  the project's offline-first static asset policy. Reduce
  `.hero-title` from `3.75rem`/`800` weight down to something in the
  `2.25rem`–`2.5rem` range, and cut `.hero-section` padding from `6rem`
  to roughly `2rem`–`2.5rem` — see Section 3.
- **Elevation/radius**: unchanged (`rounded-xl`, existing shadow
  values), recalibrated only where they currently hardcode the old
  blue accent (e.g. `.skill-card:hover` box-shadow ring color already
  reads `var(--accent)`, so no hardcoded value to change there).
- **No new Tailwind utility classes.** Anything new (category badge,
  featured-shelf heading, version-list panel) is added as explicit
  classes in `app.css`, following the existing `.install-modal-*`
  pattern of self-contained styles that don't depend on the
  JIT-purged vendor bundle.

## 2. Backend data model (additive, small)

- `parser.py::_get_default_icon(skill_name, meta)` is renamed
  `_classify(skill_name, meta)` and returns `(icon, category)` instead
  of just `icon`. It reuses the exact same 8 keyword-group table,
  giving each group an explicit category name:

  | Keywords | Icon | Category |
  |---|---|---|
  | design, art, theme, css, style, canvas, factory | 🎨 | Design |
  | tool, util, convert, pdf, docx, xlsx, pptx, zip | 🔧 | Tools |
  | code, dev, build, script, api, mcp, skill | 💻 | Code |
  | content, doc, write, comms, brand, internal | 📝 | Content |
  | test, qa, check, verify | 🧪 | Testing |
  | ai, ml, chat, claude, bot, data, algorithm | 🤖 | AI/ML |
  | slack, comm, message, gif | 💬 | Communication |
  | git, repo, version | 📦 | Other |
  | *(no match / fallback)* | 📦 | Other |

  If `meta['icon']` is explicitly set in `SKILL.md` frontmatter (the
  existing override path), category still falls back to keyword
  classification against the skill name — `SKILL.md` has no category
  field today and this design doesn't add one.

- `parser.py::parse_skill_from_dir` return dict gains a `'category'`
  key.
- `views.py::_LIST_FIELDS` gains `'category'` so it's projected into
  the catalog list view (and therefore the `#skills-data` JSON blob
  `home.js` reads).
- `views.py::home`: after building `skills`, compute
  `featured = sorted(skills, key=lambda s: s['lastUpdated'] or '', reverse=True)[:4]`
  and pass both `skills` and `featured_skills` in the render context.
  This is a pure slice of already-fetched data — no new query path, no
  `usage.py` involvement, watcher-driven catalog updates flow through
  exactly as before.
- Existing tests (`test_parser.py`, `test_views.py`) get updated
  assertions for the new `category` field (present, one of the 8 known
  values); no new test framework or fixtures.

## 3. Home page (`home.html` + `home.js`)

- **Header**: unchanged structurally (logo, always-visible search,
  Contribute/Installed nav links, theme toggle) — research confirms
  persistent search is the stronger pattern (VS Code, Claude Plugins).
  Re-skinned to the new accent/spacing only.
- **Hero**: replaced with a compact one-line kicker directly under the
  header ("Discover, share, and install AI-powered skills") — no
  duplicate giant title, since search already lives in the sticky
  header. Removes the current visual redundancy between header and
  hero.
- **Featured shelf**: new section titled "Featured", rendering
  `featured_skills` (up to 4 cards) using the same card partial/markup
  as the main grid. Server-rendered, hidden entirely when the catalog
  has 4 or fewer skills total (no value in shelving everything).
- **All skills grid**: existing grid, re-labeled "All skills". Gains a
  `Category` `<select>` next to the existing `Sort` `<select>`,
  populated from the 8 known category values. Filtering is
  **client-side** in `home.js`, following the exact same pattern as
  the existing `sortSelect` `change` listener — a `currentCategory`
  variable, applied in `render()`'s `.filter(...)` alongside the
  existing search filter. No new endpoint, no separate Apply button
  (a single dropdown doesn't need one — the "Apply, don't live-filter"
  research finding applies to multi-checkbox filter rails, not a
  single select).
- **Card**: gains a small category badge (reusing pill styling similar
  to `.version-select`) shown next to the icon. No other fields added —
  per research, 3-4 fields per card is the ceiling; icon, name,
  description, category badge, file count, and updated-time is already
  at that ceiling, so nothing else goes on the card.

## 4. Skill detail page (`skill_detail.html` + `skill.js`)

- Replace `<select id="version-select">` with a small popover pattern:
  a pill button reading `v{currentVersion}` that expands a vertical,
  reverse-chronological list of all versions (`.version-list-item`),
  with the active version visually pinned at the top with a "current"
  badge — mirroring PyPI's release-list pattern. Same underlying
  `skill.versions` data, same `?version=` query-param navigation
  behavior; `skill.js`'s existing version-switch handler is retargeted
  from a `change` event on a `<select>` to a `click` event on list
  items, but the navigation logic itself (build URL, `location.href`)
  is unchanged.
- File explorer, content panel, install/download buttons, install
  modal: re-skinned only (new accent color, tightened spacing) — no
  structural change.

## 5. Other pages

`installed.html`, `contribute.html`, `usage.html`,
`admin_contributions.html`, `contribution_detail.html`,
`my_contributions.html`: re-skin only, inherited automatically from
the updated CSS variables plus any direct references to the old
`#2563eb`/`#1d4ed8` literals (e.g. `.installed-uninstall-btn` and
danger-state colors use hardcoded `#b42318` reds, which are
intentionally left unchanged — they're a semantic danger color, not
the brand accent). No layout restructuring this round.

## Testing & verification

- Update `test_parser.py` / `test_views.py` for the new `category`
  field.
- Re-run `skills/static/skills/dev/install-modal-ui-audit.js` in
  DevTools after the modal re-skin (must return `{passed: 64+, failed:
  0}`), since accent-color and spacing changes touch the same markup
  that audit covers.
- Manual verification: load home page and a skill detail page at
  ~1280px and ~375px, in both light and dark theme, console clean —
  per house UI-verification rule. Confirm Featured shelf hides
  correctly on a catalog with ≤4 skills (use a temp filter or count
  check), category filter narrows the grid correctly, and the new
  version-list popover on skill-detail navigates the same as the old
  dropdown did.

## Out of scope (explicitly deferred)

- Restructuring `installed`/`contribute`/`usage`/admin pages beyond
  re-skinning.
- Any install-count-based "most popular" ranking (would require new
  `usage.py` query logic) — Featured uses `lastUpdated`, decided
  explicitly over usage-based ranking to avoid new backend surface.
- A sidebar filter rail (Hugging-Face style) — deferred as
  disproportionate for the current catalog size; a single Category
  dropdown covers the need today.
