# Skill Market — Improvement Backlog

Internal-network deployment notes. Items are ordered by usability impact, not
implementation effort. Items 2 / 3 / 4 from the original review have shipped
and are not listed here.

## Done

- **Remove Copy buttons** on skill detail page — the install commands are now
  shown plain, no clipboard interaction.
- **Category & icon from frontmatter** — `SKILL.md` can declare `category:`
  and/or `icon:` and they win over `classifier.CATEGORY_MAP`. Adding a brand-new
  skill with a brand-new category no longer requires a Python edit; new
  categories also auto-appear as filter pills.
- **Search inside SKILL.md body** — both `/api/skills?search=` and the home
  page client-side filter now match against the markdown content. Results are
  ranked name > description > content.
- **Keyboard shortcuts** — `/` or `Ctrl+K` focuses the search box on the home
  page; `Esc` clears + blurs the search; on the detail page `Esc` returns to
  the catalog and `D` triggers Download ZIP. Hints are surfaced inline (a `/`
  badge in the search box, `Esc` next to Back, `D` next to Download).

## Still TODO — high impact

### A. One-line install command  (deferred — needs decision)

`backend/skills/views.py::_install_paths` currently produces

    cp -r "<server-side absolute path>" "~/.claude/skills/<name>"

The source path lives on the Django host, so colleagues on the LAN can't
actually run it. A useful internal-network install is one of:

```bash
# unzip directly into the target dir
curl -sL http://<host>/api/skills/<name>/zip | bsdtar -xf - -C ~/.claude/skills/

# or, if bsdtar isn't available, two lines
curl -sLO http://<host>/api/skills/<name>/zip && unzip -o <name>.zip -d ~/.claude/skills/
```

Implementation touch points:

- `frontend/skill.js` — replace the `cp -r` template in `renderSkill()` with a
  curl-based one. Keep two tabs (Claude Code / Opencode) — only the target
  directory differs.
- The host portion needs to be discoverable. Either render it server-side into
  the page, or read `window.location.host` from JS (simpler, no template
  changes).
- `frontend/skill.html` — the install section can drop the "Install Paths"
  sidebar card since the path now lives in the command.

### B. Lazy-render the Files section

`frontend/assets/skill.js::load()` parallel-fetches the detail JSON **and**
`/files` (full text body of every file) on every page load. For skills with
many files or long markdown this is a meaningful payload the user may never
look at.

Suggested change:

- Render the Files section as a list of collapsed rows (filename + language
  pill + chevron). Body is fetched / rendered on first expand.
- Cheapest path: still fetch the file list eagerly so we know how many rows
  to render, but switch the `/files` endpoint to return metadata only by
  default and add `?include=content` (or a per-file `/files/<path>` endpoint)
  for the on-demand expand.

## Still TODO — medium impact

### C. Tags in frontmatter

A skill currently belongs to exactly one category. Many real skills sit on a
boundary (testing + development, content + tools). Adding an optional
`tags: [a, b, c]` array in `SKILL.md` frontmatter and rendering them as small
pills (clickable to filter) would solve this without breaking the single-
category model.

- `parser.parse_skill_from_dir` — read `meta.get('tags') or []`.
- `views.api_skill_list` — accept `?tag=` filter; include tag in list payload.
- `home.js` — extra filter row of tag pills, OR-combined with category.

### D. Card hint when a skill has versions

`home.js::cardHtml` doesn't surface whether a skill has version history. A
small `v3` chip on the card would let users know without opening the detail.
Data is already in `skill.versions`.

### E. Long-doc TOC on the detail page

For long `SKILL.md` files the markdown body becomes a wall of text. After
`window.marked.parse(skill.content)` runs, walk the rendered headings (h2/h3)
and inject a sidebar / sticky TOC in the right-hand column. Anchor IDs can be
derived from heading text — `marked` already wraps headings.

## Still TODO — low impact / hygiene

### F. `classifier.CATEGORY_MAP` is now optional

With item 2 shipped the hardcoded map only acts as a default for the existing
17 skills. Once each `SKILL.md` declares its own `category` / `icon`, the map
can be deleted. Until then, leaving it in place keeps existing behavior.

### G. Stale repo files

- `client/` — leftover `node_modules` from the pre-Django React/Vite stack.
  CLAUDE.md already documents that the stack changed; the directory can go.
- `README.md` — still describes the Node/Express + React/Vite layout and
  `node manage.js` workflow. Should be replaced with a short Django-era
  README (or just point at CLAUDE.md).
- `plan.md`, `spec.md` — both describe the original stack. Either delete or
  archive under `docs/` with a note.

### H. E2E hard-codes a Linux Chromium binary

`backend/e2e/conftest.py` sets

    CHROMIUM_EXEC = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'

so `pytest e2e/` will not run on Windows or macOS. Read from an env var
(`CHROMIUM_EXEC`) with a `playwright install`-style auto-detect fallback so
the test suite is portable.

### I. `test_file_reader.py::test_read_subdirectories` fails on Windows

Asserts `'/' in path`, but `read_skill_files` returns paths with the OS
separator. Use `os.sep` or normalize to `/` in the reader (cleaner — the API
shape stays predictable across platforms).

### J. Show file size in the sidebar

Sidebar has Files count but not total size. Cheap to add via
`os.walk` + `os.path.getsize` in `parser._count_files`.

## Notes for future work

- Search currently runs entirely client-side after the initial fetch (the list
  endpoint returns full `content` for that reason). For a much larger catalog
  (hundreds of skills) this stops being free — switch to debounced server-side
  search via `/api/skills?search=`. The backend already supports it.
- The watcher debounces FS events at 300ms. If a future feature stages many
  files at once (e.g. a bulk import script), revisit this — currently fine.
