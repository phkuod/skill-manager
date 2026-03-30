# Skill Document View — File Blocks Design

**Date:** 2026-03-30
**Status:** Approved

## Summary

Replace the single-markdown documentation block in the skill detail view with a flat list of per-file blocks, one block per file in the skill directory. Markdown files are rendered as rich markdown; all other files are shown as raw code blocks.

## API

### New endpoint: `GET /api/skills/:name/files`

Returns an ordered array of file descriptors for all non-binary files in the skill directory (recursive):

```json
[
  { "path": "SKILL.md", "content": "...", "language": "markdown" },
  { "path": "shared/models.md", "content": "...", "language": "markdown" },
  { "path": "LICENSE.txt", "content": "...", "language": "text" },
  { "path": "python/example.py", "content": "...", "language": "python" }
]
```

**Ordering:** `SKILL.md` always first, then all other files sorted alphabetically by path.

**Language inference:** derived from file extension:
- `.md` → `markdown`
- `.py` → `python`, `.ts` / `.tsx` → `typescript`, `.js` / `.jsx` → `javascript`
- `.go` → `go`, `.rb` → `ruby`, `.java` → `java`, `.cs` → `csharp`, `.php` → `php`
- `.sh` → `bash`, `.json` → `json`, `.yaml` / `.yml` → `yaml`
- unknown / `.txt` → `text`

**Binary file exclusion:** files detected as binary (images, ZIPs, etc.) are omitted entirely.

**Size limit:** files larger than 500 KB are included with `content: null` and a `truncated: true` flag.

## Frontend

### Changes to `SkillDetail.jsx`

The "Documentation" section is replaced with a `<SkillFiles>` component (or inline map) that:

1. Fetches `/api/skills/:name/files` on mount
2. Renders a flat list of file blocks, each containing:
   - **Header bar**: relative file path (e.g. `shared/models.md`) + language badge
   - **Body**:
     - `language === 'markdown'` → `<ReactMarkdown>` with `remarkGfm`
     - all others → `<pre><code>` with language label
     - `truncated === true` → notice: _"File too large to preview"_

The existing `skill.content` field (SKILL.md content embedded in the skill detail response) is no longer used for the documentation section.

### Loading & error states

- While fetching: show a loading skeleton in place of the file list
- On fetch error: show an inline error message
- Empty result (no files): show a "No files found" notice

## Edge Cases

| Scenario | Behaviour |
|---|---|
| Skill with only `SKILL.md` | One block rendered, same as before |
| Binary files in skill dir | Skipped, not included in response |
| File > 500 KB | Block shown with "File too large to preview" |
| Fetch failure | Inline error message in documentation section |

## Out of Scope

- Syntax highlighting (color themes) — plain `<pre><code>` is sufficient for now
- Collapsible/expandable file blocks
- File tree / sidebar navigation
