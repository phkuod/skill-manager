# Full UI/UX Redesign — Design Spec

Date: 2026-07-10
Status: Approved (all five sections approved in brainstorming session)
Branch: `refactor/flatten-backend` (in-place, same convention as the 2026-07-06
modernization and 2026-07-08 refinement rounds)

## Goal

A true redesign of the Skill Market frontend: new visual identity **and** new
page layouts across **all nine templates**, plus three functional UX upgrades
(command palette, category rail, sticky detail sidebar). The site should feel
like a different, better product afterward — a crisp developer tool in the
Linear/Vercel vein.

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Boldness | New identity + new layouts |
| Scope | All pages: home, skill_detail, installed, contribute, my_contributions, contribution_detail, admin_contributions, usage, 404 |
| CSS strategy | Regenerate the Tailwind vendor bundle once via standalone CLI; re-vendor output |
| Identity | Crisp developer-tool (near-black dark, electric sky-blue accent) |
| Fonts | Vendor self-hosted Inter variable + JetBrains Mono variable (woff2, OFL) |
| Depth | Templates + frontend JS + tests evolve together; **backend untouched** |
| UX features | ⌘K command palette, category rail on home, sticky detail sidebar |
| Styling architecture | Design tokens + named component classes; Tailwind utilities only for one-off layout |

## Non-goals / hard constraints

- **No backend changes**: `views.py`, `urls.py`, all `/api/*` endpoints,
  `parser.py`, `watcher.py`, `installer.py`, `zipper.py`, cookie auth, and the
  install/uninstall flows are untouched. Same data, same endpoints, same
  behavior.
- No CDN or network-loaded assets — all fonts and libraries vendored.
- No permanent build step — the Tailwind regen is a documented one-time
  (repeatable) CLI operation, not a watch/build pipeline.
- Light + dark themes both fully supported, same `.dark`-class mechanism.
- Existing accessibility ground rules carry over: focus-visible ring system,
  `prefers-reduced-motion` support, aria labels.

## 1. Visual identity system (tokens)

### Color

Clean break from indigo/slate. All values land as CSS custom properties in a
token block; dark mode is pure token swapping.

Light theme:
- Canvas `#fafafa` (cool near-white); panels/cards `#ffffff`
- Hairline borders `#e4e4e7`
- Text `#0f0f11` primary, `#6b7280` muted
- Accent **electric sky-blue `#0284c7`**

Dark theme:
- Canvas `#0a0a0c` (true near-black, not slate); panels `#131316`
- Hairline borders `rgba(255,255,255,.08)`
- Text `#ededf0` primary, muted gray secondary
- Accent `#38bdf8`

Accent is used sparingly: primary buttons, focus rings, active states, links.
Semantic green/amber/red kept for install states and admin status chips,
re-tuned to sit on the new palette.

### Typography

- **Inter variable** (vendored) for all UI. Headings tight-tracked (−0.02em),
  weights 550–650. Scale: 32 / 24 / 18 / 15 / 14 px.
- **JetBrains Mono variable** (vendored) for everything "data": code blocks,
  file names, version dates, counts, category/license badges, install target
  paths. Mono metadata is the signature of the identity.

### Surfaces, depth, radii

- Borders over shadows: 1px hairlines define cards and panels.
- Shadows reserved for true overlays: command palette, popovers, modals.
- Radii: 8px cards / 6px controls (down from today's 12px+).
- Emoji skill icons (data from `classifier.py`) stay, presented in a neutral
  bordered tile.

### Motion

120–160ms ease-out transitions on interactive states only.
`prefers-reduced-motion: reduce` disables transforms/transitions (carried
over from the refinement round).

## 2. Page layouts

### Shared shell (`base.html`)

Centralize one sticky top nav in the base template (today each page rolls its
own `{% block header %}`):

- Left: wordmark "Skill Market".
- Nav links: Browse, Installed, Contribute; admin links (Review, Usage) shown
  to admins (same conditional data the current templates use).
- Right: search button labeled with `⌘K`, theme toggle, user chip.
- Sticky, hairline bottom border, slight backdrop blur.
- Footer slims to a single mono line (keeps `#footer-count` behavior).
- Command palette markup lives here too (see §3).

### Home

- Tall gradient hero removed. Compact page header: "Browse skills" + mono
  count.
- Two-zone layout: **category rail** left (desktop ≥1024px), card grid right
  with a slim toolbar (sort select + result count).
- Under 1024px the rail becomes a horizontal chip scroller above the grid.
- Featured skills: pinned first row of the grid with a subtle accent tag
  (separate Featured shelf removed).
- Cards densify: icon tile + name + 2-line description + mono footer
  (category · file count · date); quick-install button appears on hover/focus.

### Skill detail

- Two-column: README + file explorer in the main column; **sticky right
  sidebar** with install CTA, download, version picker, mono metadata list
  (category, license, files, updated, install targets), and README / Files
  anchor links.
- Breadcrumb back to Browse.
- Below 1024px the sidebar renders as a normal block above the content.

### Installed

- Cards become a dev-tool **row list** grouped by install target: mono path,
  skill name, installed date, uninstall action per row.

### Contribute family

- `contribute.html`: single-column flow kept; cleaner dropzone; requirements
  checklist.
- `my_contributions.html` and `admin_contributions.html`: status-chip row
  tables with segmented-control filters.
- `contribution_detail.html`: comment thread styled as an activity feed with
  role-colored chips; sticky action bar for admin state transitions.

### Usage

- KPI row with large mono numbers; existing tables/lists restyled to match.

### 404

- Minimal mono treatment.

## 3. UX feature behavior

### Command palette (⌘K / Ctrl-K)

- Global: markup in `base.html`, logic in `common.js` — works on every page.
- Opens via shortcut or the nav search button.
- On first open, fetches `/api/skills` once per page load (catalog is small
  and in-memory); client-side matching — no library: case-insensitive
  substring match, name matches ranked above description matches, ties
  broken alphabetically.
- Results: icon, name, category chip, mono file count. ↑/↓ + Enter navigates
  to `/skills/<name>/`; Esc or click-outside closes.
- Accessibility: `role="dialog"`, `aria-modal`, focus trapped while open,
  focus restored to the trigger on close.
- No backend changes.

### Category rail (home)

- Replaces the `#category-select` dropdown.
- Server-rendered from existing context via `{% regroup %}` — no view
  changes. "All" plus each category with count.
- Click filters the grid client-side (rewiring existing `home.js` filter
  logic), sets `?category=` in the URL (shareable/bookmarkable), accent +
  `aria-current` on the active item.
- Deep link `/?category=X` arrives pre-filtered.
- Composes with the existing search box as AND: rail picks the category,
  search narrows within it (same semantics the select + search have today).

### Sticky detail sidebar

- Pure `position: sticky` below the nav — no JS for stickiness.
- Hosts the existing install-modal trigger, download link, and version
  popover: current logic preserved, relocated.
- README / Files anchor links smooth-scroll (instant under reduced-motion).

## 4. Architecture & build

### CSS

- New `skills/static/skills/css/tokens.css`: all custom properties for both
  themes + `@font-face` rules.
- `skills/static/skills/css/app.css` rewritten: named component classes
  (`.nav`, `.card`, `.rail`, `.palette`, `.sidebar`, `.btn-*`, `.chip`, …)
  organized per page family. Tailwind utilities only for one-off layout
  (flex/grid/gap).
- Load order: tailwind vendor → hljs theme → tokens.css → app.css.
- Dark mode: existing `.dark`-class-on-`<html>` + pre-paint script + hljs
  theme swap, unchanged.

### Fonts

- `skills/static/skills/vendor/fonts/`: `InterVariable.woff2`,
  `JetBrainsMono[wght].woff2`, plus OFL license files. `font-display: swap`.

### Tailwind regen

- After templates are rewritten: run the standalone Tailwind CLI once
  (single binary, one-time download) scanning `skills/templates/**` and
  `skills/static/skills/js/**`; output replaces `vendor/tailwind.min.css`.
- The regen command gets documented in CLAUDE.md — the frozen-bundle trap
  becomes a known, repeatable operation.

### Single card renderer

- Replace the dual renderer (`_skill_card.html` + `home.js::cardHtml()`
  string) with one HTML `<template>` element rendered by the server partial
  and cloned by JS. One source of truth for card markup.

### JS

- `common.js`: + palette module.
- `home.js`: filter logic rewired to the rail; `<template>` cloning replaces
  `cardHtml()`.
- `skill.js`: install/version logic relocated into the sidebar, behavior
  unchanged.
- `installed.js`: renders the new row list.

### Dev tooling / docs

- `skills/static/skills/dev/install-modal-ui-audit.js` updated to the new
  markup and re-baselined; CLAUDE.md's stale "64+" audit figure corrected;
  known headless caveats (cookie injection, `.env.development` sourcing)
  documented alongside.

## 5. Testing & verification

### Unit tests

- Every template change updates its string-assertion tests in
  `skills/tests/` in the same task (TDD: assert new markup → fails →
  implement → passes).
- New tests: palette markup present via base template; rail renders all
  categories with correct counts; detail sidebar structure; `<template>`
  card renderer; `?category=` initial-state rendering.

### E2E (Playwright)

- Existing e2e tests: selectors updated as markup changes.
- New scenarios: Ctrl-K opens palette → type → Enter navigates to the right
  skill → Esc closes and restores focus; rail click filters grid and updates
  URL; deep-link `/?category=X` pre-filtered; install modal completes from
  the new sidebar; uninstall works from the new installed row list.

### Visual gate (real browser, real flows — standing user feedback)

After the final task:
- Screenshots of **all nine pages** at 1280px and 375px, light **and** dark.
- Browser console clean.
- Keyboard tab-through showing focus rings.
- Reduced-motion check.
- Font-loading check: woff2 actually served, no layout shift.
- Install-modal audit script re-baselined and run.

### Regen sanity

- Diff old vs new Tailwind bundle class lists to confirm nothing
  still-referenced was dropped.
- Full unit + e2e suites against the regenerated CSS.

Full pytest suite green before every commit.
