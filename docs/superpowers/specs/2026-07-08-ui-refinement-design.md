# UI Refinement — Execution Polish Pass

**Date:** 2026-07-08
**Status:** Approved for planning

## Goal

Second-round visual polish on top of the 2026-07-06 modernization
(`2026-07-06-ui-modernization-design.md`). The identity stays exactly as
it is — indigo/violet accent, slate neutrals, system fonts — this round
tightens *execution*: spacing rhythm, typographic hierarchy, focus
states, and the handful of layout rough edges left behind by the last
round. Approach chosen: **CSS + surgical template polish** (approach B)
— `app.css` work plus targeted markup edits, **no JS logic changes, no
backend changes, no new routes, no new dependencies**.

## Scope

Hands-on polish: `home.html`, `_skill_card.html`, `skill_detail.html`,
`app.css`, and the markup-only `cardHtml()` template string in
`home.js`. All other pages (`installed`, `contribute`, `usage`, admin
pages) inherit shared-CSS improvements only.

Standing constraints (unchanged from last round):

- The vendored Tailwind bundle is JIT-purged and frozen — no new
  utility classes; anything new is an explicit class in `app.css`.
- No web fonts, no CDNs.
- JS/e2e selector contract must survive: `.skill-card`,
  `.quick-install-btn`, `.skill-card-targets`,
  `.inline-confirm-row[data-confirm-slot]`, `#category-select`,
  `#sort-select`, `#result-count` (text format `Showing X of Y`),
  `#files-section`, `#content-section`, `#file-count-badge`,
  `#content-panel-title`, `#version-popover*`, `.license-badge`,
  `.category-badge`, install-modal IDs/classes.

## 1. Shared CSS polish (`app.css`)

- **Focus-visible system.** One shared rule set: interactive elements
  (`a`, `button`, `select`, `input`, `[role="option"]`, the popover
  trigger/items) get `outline: 2px solid var(--accent);
  outline-offset: 2px` on `:focus-visible` only. No outline on mouse
  focus. The search input keeps its existing focus ring; the shared
  rule must not double-ring it.
- **Reduced motion.** `@media (prefers-reduced-motion: reduce)`
  disables transform/transition animation site-wide (card lift, modal
  scale-in, spinners keep functional visibility but drop motion).
- **Pill unification.** `.category-badge`, `.license-badge`,
  `.version-popover-trigger`, `.installed-target-type`,
  `.installed-card-badge` converge on one metric set (padding
  `2px 10px`, radius `999px`, `font-size: 0.7rem`, weight 600,
  `var(--bg-secondary)` fill, `var(--border)` stroke) — implemented as
  shared declarations, not necessarily one class, to avoid template
  churn on out-of-scope pages.
- **Markdown typography** (`.skill-markdown`): clearer heading steps
  (h1 1.6rem / h2 1.3rem with a hairline `border-bottom:
  1px solid var(--border)` / h3 1.1rem), body `line-height: 1.65`,
  `pre` padding to 1rem–1.25rem with radius 10px, table header row
  keeps `--bg-secondary` but adds a slightly stronger bottom border.
- **Cleanup.** Merge the duplicated `body { }` rules (currently lines
  ~40 and ~459 — drifted copies; the merged rule keeps `margin: 0` and
  `letter-spacing: -0.01em` plus the theme transition). Remove the dead
  `.install-tab` / `.install-tab.active` rules — their markup was
  removed in the last round (`fde7741`).

## 2. Home page (`home.html`, `_skill_card.html`, `home.js` markup string)

- **Card layout.** The category badge moves from the cramped top row to
  the footer meta row: footer becomes category badge (left) + file
  count and date (right). Top row becomes icon + install-target pills
  (left) + quick-install button (right), vertically centered; the
  leftover `margin-bottom: 1rem` on `.icon-wrapper` is neutralized in
  card context (`.skill-card .icon-wrapper { margin-bottom: 0 }` or
  equivalent — the detail-page 80px icon usage keeps its own spacing).
  `home.js::cardHtml()` is updated to emit the identical structure —
  markup only; no logic, listener, or state changes.
- **Toolbar.** Left: `All skills · <count>` (count styled secondary,
  sourced from the same server-rendered number). Right: the two
  `<select>`s restyled to a consistent 32px-ish height, shared radius
  and hover/focus treatment; the visible `Category:` / `Sort:` labels
  are replaced by `aria-label`s on the selects. `#result-count` element
  and its `Showing X of Y` format are preserved (it may move within the
  toolbar but keeps id and format).
- **Hero kicker.** Kept, tightened: vertical padding roughly halved
  (`1.75rem 1.5rem 1.25rem` → `~0.9rem 1.5rem 0.6rem`), font-size
  0.95rem, so the Featured shelf starts higher.

## 3. Skill detail page (`skill_detail.html`)

- **Quiet panel headers.** The macOS traffic-light dots in the
  file-explorer and content panel headers are replaced by: small inline
  SVG glyph (folder for files, document for content) + panel title on
  the left; metadata on the right (`#file-count-badge` in the files
  panel; a small `readonly` chip in the content panel). Monospace
  header font stays. All functional IDs and the collapse
  chevron/`toggleFileExplorer()` wiring are untouched.
- **Action row.** The inline-styled button row becomes
  `<div class="detail-actions">` with two new `app.css` classes:
  `.btn-accent` (filled accent — Install) and `.btn-outline` (bordered
  — Download ZIP), each with hover, active (1px translate), and
  focus-visible states. `#install-button` / `#download-link` IDs and
  behavior unchanged.
- **Hero rhythm.** Gap/margins around the icon–name–badges block put on
  a consistent 0.25/0.5/0.75/1rem rhythm; the description gets
  `max-width: 65ch` for a readable measure.

## Testing & verification

- `pytest skills/tests/` green — existing assertions (`category-badge`
  in body, `license-badge`, `version-popover`, featured-shelf strings)
  keep passing because the class names and IDs survive.
- `pytest e2e/` green (19 tests) — selector contract preserved by
  design.
- Re-run `skills/static/skills/dev/install-modal-ui-audit.js` on a
  detail page: `{passed: 64+, failed: 0}` (shared CSS could shift modal
  rendering).
- Real-browser visual pass per house rule: `/` and one skill detail
  page at ~1280px and ~375px, light **and** dark theme, console clean.
- Keyboard-only pass: tab through header → search → toolbar → cards →
  (detail) actions → version popover; every stop shows the new
  focus-visible ring; popover keyboard nav (added in `9a6b1cd`) still
  works.
- Reduced-motion spot check (DevTools emulation): card hover no longer
  translates, modal appears without scale animation.

## Out of scope (explicitly deferred)

- Layout restructuring of `installed` / `contribute` / `usage` / admin
  pages (they get shared-CSS inheritance only).
- Any JS behavior change: animated filtering, skeletons, sticky
  toolbar (approach C items).
- Palette, icon set, or brand identity changes.
- New card fields or data model changes (`parser.py`, `views.py`
  untouched).
