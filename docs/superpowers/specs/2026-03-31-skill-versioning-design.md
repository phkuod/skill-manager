# Skill Versioning Design Spec

## Overview

Add version control capability to skills in `skill_repo/`. Skills can optionally have versioned sub-directories named `yyyymmdd-<description>` to define new versions. The latest dated sub-directory becomes the current version. Skills without version sub-directories maintain their existing flat structure unchanged.

## Goals

- Support versioned skills via `yyyymmdd-*` sub-directories within a skill folder
- Backward compatible: unversioned skills work exactly as before
- Web UI allows browsing and switching between versions
- Install/download targets the user-selected version

## Non-Goals

- No migration tool to convert existing skills into versioned format
- No version diffing or changelog generation
- No version pinning or locking mechanism

## Directory Structure

### Unversioned skill (no change)

```
skill_repo/
  algorithmic-art/
    SKILL.md
    templates/
```

### Versioned skill

```
skill_repo/
  frontend-design/
    SKILL.md                          ← original version
    templates/
    20260401-improved-prompts/
      SKILL.md                        ← version content (complete, self-contained)
      templates/
    20260415-dark-mode/
      SKILL.md
      templates/
```

### Version Rules

1. Version sub-directory naming: `/^\d{8}-.+/` (8-digit date + `-` + description)
2. Each version sub-directory is a complete, self-contained skill (has its own `SKILL.md` and all files)
3. Current version = the sub-directory with the latest date (sorted descending)
4. Root-level files are preserved as the "original" version when version sub-directories exist
5. The original version appears last in the version list, labeled `original`
6. A version sub-directory without `SKILL.md` is ignored

## Parser Changes (`server/parser.js`)

### New function: `detectVersions(skillDir)`

Scans the skill directory for sub-directories matching `/^\d{8}-.+/`, validates each has a `SKILL.md`, and returns them sorted by date descending.

```js
// Returns:
[
  { version: "20260415-dark-mode", path: "/abs/path/...", date: "20260415" },
  { version: "20260401-improved-prompts", path: "/abs/path/...", date: "20260401" },
]
```

### Refactored: `parseSkillFromDir(dir, skillName)`

Extract the existing `SKILL.md` reading logic into a reusable function that accepts any directory path.

### Modified: `parseSkill(skillDir, skillName)`

```
if version sub-directories found:
  read SKILL.md from the latest version sub-directory
  attach currentVersion and versions list to skill data
else:
  read SKILL.md from root (existing behavior)
  set currentVersion = null, versions = []
```

### Skill Data Shape (updated)

```json
{
  "name": "frontend-design",
  "description": "...",
  "category": "Development",
  "icon": "🎨",
  "license": "Complete terms in LICENSE.txt",
  "fileCount": 3,
  "lastUpdated": "2026-04-15T...",
  "currentVersion": "20260415-dark-mode",
  "versions": [
    { "version": "20260415-dark-mode", "date": "20260415" },
    { "version": "20260401-improved-prompts", "date": "20260401" },
    { "version": "original", "date": null }
  ]
}
```

Unversioned skills return `currentVersion: null` and `versions: []`.

## API Changes (`server/app.js`)

### New endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/skills/:name/versions` | List all versions of a skill |
| GET | `/api/skills/:name/versions/:version` | Get full skill data for a specific version |
| GET | `/api/skills/:name/versions/:version/zip` | Download a specific version as ZIP |
| GET | `/api/skills/:name/versions/:version/files` | List files in a specific version |

### `GET /api/skills/:name/versions` response

```json
{
  "skill": "frontend-design",
  "currentVersion": "20260415-dark-mode",
  "versions": [
    { "version": "20260415-dark-mode", "date": "20260415" },
    { "version": "20260401-improved-prompts", "date": "20260401" },
    { "version": "original", "date": null }
  ]
}
```

### `GET /api/skills/:name/versions/:version` response

Same shape as `GET /api/skills/:name` but reads from the specified version directory. `:version` accepts version names like `20260415-dark-mode` or `original`.

### Version directory resolution helper

```js
function resolveVersionDir(skillRepoPath, skillName, version) {
  if (version === 'original') {
    return resolve(skillRepoPath, skillName);
  }
  return resolve(skillRepoPath, skillName, version);
}
```

### Existing endpoints (unchanged behavior)

- `GET /api/skills` — list includes `currentVersion` and `versions` fields per skill
- `GET /api/skills/:name` — returns current (latest) version data
- `GET /api/skills/:name/zip` — downloads current version
- `GET /api/skills/:name/files` — lists current version files

## Zipper Changes (`server/zipper.js`)

Change `sendZip(res, skillRepoPath, skillName)` to accept a resolved directory path: `sendZip(res, dirPath, zipName)`. The caller resolves the correct directory (root or version sub-directory) before calling.

## FileReader Changes (`server/fileReader.js`)

Same pattern as zipper: `readSkillFiles(skillRepoPath, skillName)` updated to accept a resolved directory path, or an optional version parameter.

## Watcher (`server/watcher.js`)

No changes needed. chokidar already watches `skill_repo/` recursively (depth: 5). Adding/modifying version sub-directories triggers the existing rebuild flow, which calls `parseAllSkills()` — now version-aware.

## Frontend Changes

### Skill Detail Page (`client/src/pages/SkillPage.jsx`)

When `versions.length > 0`, render a **version selector** between the skill header and content:

1. **Dropdown/select** listing all versions
   - Latest version marked with `(latest)`
   - `original` displayed as `original`
   - Current version pre-selected
2. **On version change**: call `GET /api/skills/:name/versions/:version` and update:
   - Description
   - SKILL.md content
   - File list
   - Install commands (paths point to version sub-directory)
   - ZIP download URL
3. **Install command paths** reflect the selected version:
   - `cp -r .../skill_repo/frontend-design/20260415-dark-mode/ ~/.claude/skills/frontend-design/`

### Home Page

- No version info on skill cards (keep it clean)
- `lastUpdated` reflects the current version's timestamp

### Unversioned skills

- No version selector rendered; page behaves exactly as today

### Hooks (`client/src/hooks/useSkills.js`)

Add functions for version-related API calls:
- `fetchVersions(skillName)` → `GET /api/skills/:name/versions`
- `fetchVersion(skillName, version)` → `GET /api/skills/:name/versions/:version`

## Testing

### Parser tests
- `detectVersions()`: correctly identifies and sorts version directories
- `detectVersions()`: ignores directories not matching the pattern
- `detectVersions()`: ignores version directories without `SKILL.md`
- `parseSkill()`: versioned skill reads from latest version
- `parseSkill()`: unversioned skill works as before (backward compat)
- `parseSkill()`: versions list includes `original` entry

### API tests
- `GET /api/skills/:name/versions` returns version list
- `GET /api/skills/:name/versions/:version` returns correct version data
- `GET /api/skills/:name/versions/:version` returns 404 for nonexistent version
- `GET /api/skills/:name/versions/original` returns root-level skill data
- Existing endpoints still work for both versioned and unversioned skills

### Frontend tests
- Version selector renders only for versioned skills
- Version switch updates displayed content
- Install commands reflect selected version path
