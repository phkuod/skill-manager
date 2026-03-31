# Skill Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add version control to skills via `yyyymmdd-*` sub-directories, with backward compatibility for unversioned skills.

**Architecture:** Extend `parser.js` with version detection logic. Add version-specific API endpoints in `app.js`. Add a version selector dropdown in the Skill Detail page that switches content, install commands, and downloads.

**Tech Stack:** Node.js/Express (backend), React (frontend), Vitest + Supertest (testing)

---

### Task 1: Parser — `detectVersions` function

**Files:**
- Modify: `server/parser.js`
- Test: `server/__tests__/parser.test.js`

- [ ] **Step 1: Create versioned skill fixture in parser test**

In `server/__tests__/parser.test.js`, add fixture setup inside the existing `beforeAll`:

```js
// Inside beforeAll, after existing fixture setup:

// Versioned skill with two versions
mkdirSync(resolve(TEST_DIR, 'versioned-skill'), { recursive: true });
writeFileSync(
  resolve(TEST_DIR, 'versioned-skill', 'SKILL.md'),
  `---
name: versioned-skill
description: "Original version"
license: MIT
---

Original content.
`
);

mkdirSync(resolve(TEST_DIR, 'versioned-skill', '20260401-initial-release'), { recursive: true });
writeFileSync(
  resolve(TEST_DIR, 'versioned-skill', '20260401-initial-release', 'SKILL.md'),
  `---
name: versioned-skill
description: "First versioned release"
license: MIT
---

Version 1 content.
`
);

mkdirSync(resolve(TEST_DIR, 'versioned-skill', '20260415-dark-mode'), { recursive: true });
writeFileSync(
  resolve(TEST_DIR, 'versioned-skill', '20260415-dark-mode', 'SKILL.md'),
  `---
name: versioned-skill
description: "Added dark mode support"
license: MIT
---

Version 2 content with dark mode.
`
);
writeFileSync(
  resolve(TEST_DIR, 'versioned-skill', '20260415-dark-mode', 'helper.js'),
  'export default {}'
);

// Versioned skill with invalid version dir (no SKILL.md)
mkdirSync(resolve(TEST_DIR, 'versioned-skill', '20260420-broken'), { recursive: true });
writeFileSync(
  resolve(TEST_DIR, 'versioned-skill', '20260420-broken', 'README.md'),
  '# No SKILL.md here'
);

// Directory that looks like a version but has wrong format (no dash after date)
mkdirSync(resolve(TEST_DIR, 'versioned-skill', '20260501'), { recursive: true });
writeFileSync(
  resolve(TEST_DIR, 'versioned-skill', '20260501', 'SKILL.md'),
  `---
name: bad-format
---
`
);
```

- [ ] **Step 2: Write failing tests for `detectVersions`**

Add to `server/__tests__/parser.test.js`, updating the import to include `detectVersions`:

```js
import { parseSkill, parseAllSkills, detectVersions } from '../parser.js';
```

Add a new `describe` block after the existing `parseAllSkills` tests:

```js
describe('detectVersions', () => {
  it('should detect version directories sorted by date descending', () => {
    const versions = detectVersions(resolve(TEST_DIR, 'versioned-skill'));
    expect(versions.length).toBe(2);
    expect(versions[0].version).toBe('20260415-dark-mode');
    expect(versions[0].date).toBe('20260415');
    expect(versions[1].version).toBe('20260401-initial-release');
    expect(versions[1].date).toBe('20260401');
  });

  it('should ignore directories without SKILL.md', () => {
    const versions = detectVersions(resolve(TEST_DIR, 'versioned-skill'));
    const names = versions.map((v) => v.version);
    expect(names).not.toContain('20260420-broken');
  });

  it('should ignore directories not matching yyyymmdd-* pattern', () => {
    const versions = detectVersions(resolve(TEST_DIR, 'versioned-skill'));
    const names = versions.map((v) => v.version);
    expect(names).not.toContain('20260501');
  });

  it('should return empty array for unversioned skill', () => {
    const versions = detectVersions(resolve(TEST_DIR, 'valid-skill'));
    expect(versions).toEqual([]);
  });

  it('should return empty array for non-existent directory', () => {
    const versions = detectVersions(resolve(TEST_DIR, 'does-not-exist'));
    expect(versions).toEqual([]);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npx vitest run --config vitest.config.server.js server/__tests__/parser.test.js`
Expected: FAIL — `detectVersions` is not exported

- [ ] **Step 4: Implement `detectVersions` in parser.js**

Add to `server/parser.js`:

```js
const VERSION_PATTERN = /^\d{8}-.+/;

export function detectVersions(skillDir) {
  if (!existsSync(skillDir)) return [];

  const entries = readdirSync(skillDir, { withFileTypes: true });
  const versions = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (!VERSION_PATTERN.test(entry.name)) continue;

    const versionDir = resolve(skillDir, entry.name);
    const skillMdPath = join(versionDir, 'SKILL.md');
    if (!existsSync(skillMdPath)) continue;

    versions.push({
      version: entry.name,
      path: versionDir,
      date: entry.name.substring(0, 8),
    });
  }

  versions.sort((a, b) => b.date.localeCompare(a.date) || b.version.localeCompare(a.version));
  return versions;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npx vitest run --config vitest.config.server.js server/__tests__/parser.test.js`
Expected: All `detectVersions` tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/parser.js server/__tests__/parser.test.js
git commit -m "feat: add detectVersions to parser"
```

---

### Task 2: Parser — Refactor `parseSkill` for version awareness

**Files:**
- Modify: `server/parser.js`
- Test: `server/__tests__/parser.test.js`

- [ ] **Step 1: Write failing tests for versioned `parseSkill`**

Add to the existing `parseSkill` describe block in `server/__tests__/parser.test.js`:

```js
it('should read from latest version directory for versioned skill', () => {
  const skill = parseSkill(resolve(TEST_DIR, 'versioned-skill'), 'versioned-skill');
  expect(skill).not.toBeNull();
  expect(skill.description).toBe('Added dark mode support');
  expect(skill.content).toContain('dark mode');
});

it('should set currentVersion for versioned skill', () => {
  const skill = parseSkill(resolve(TEST_DIR, 'versioned-skill'), 'versioned-skill');
  expect(skill.currentVersion).toBe('20260415-dark-mode');
});

it('should include versions list with original entry last', () => {
  const skill = parseSkill(resolve(TEST_DIR, 'versioned-skill'), 'versioned-skill');
  expect(skill.versions).toEqual([
    { version: '20260415-dark-mode', date: '20260415' },
    { version: '20260401-initial-release', date: '20260401' },
    { version: 'original', date: null },
  ]);
});

it('should count files only in the current version directory', () => {
  const skill = parseSkill(resolve(TEST_DIR, 'versioned-skill'), 'versioned-skill');
  // 20260415-dark-mode has SKILL.md + helper.js = 2 files
  expect(skill.fileCount).toBe(2);
});

it('should set currentVersion to null for unversioned skill', () => {
  const skill = parseSkill(resolve(TEST_DIR, 'valid-skill'), 'valid-skill');
  expect(skill.currentVersion).toBeNull();
  expect(skill.versions).toEqual([]);
});
```

Also update the `parseAllSkills` test that checks size — it now includes `versioned-skill`:

```js
it('should parse all valid skills from a directory', () => {
  const skills = parseAllSkills(TEST_DIR);
  expect(skills).toBeInstanceOf(Map);
  // valid-skill, minimal-skill, nested-skill, versioned-skill (no-skill-md is skipped)
  expect(skills.size).toBe(4);
});
```

And update the `should include skills by directory name as key` test:

```js
it('should include skills by directory name as key', () => {
  const skills = parseAllSkills(TEST_DIR);
  expect(skills.has('valid-skill')).toBe(true);
  expect(skills.has('minimal-skill')).toBe(true);
  expect(skills.has('nested-skill')).toBe(true);
  expect(skills.has('versioned-skill')).toBe(true);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run --config vitest.config.server.js server/__tests__/parser.test.js`
Expected: FAIL — `currentVersion` and `versions` are undefined

- [ ] **Step 3: Refactor `parseSkill` in parser.js**

Replace the existing `parseSkill` function and extract `parseSkillFromDir`:

```js
export function parseSkillFromDir(dir, skillName) {
  const skillMdPath = join(dir, 'SKILL.md');
  if (!existsSync(skillMdPath)) return null;

  const raw = readFileSync(skillMdPath, 'utf-8');
  const { data: frontmatter, content } = matter(raw);

  const stat = statSync(skillMdPath);
  const fileCount = countFiles(dir);
  const { category, icon } = classify(skillName);

  return {
    name: frontmatter.name || skillName,
    description: frontmatter.description || '',
    license: frontmatter.license || 'Unknown',
    category,
    icon,
    fileCount,
    lastUpdated: stat.mtime.toISOString(),
    content,
  };
}

export function parseSkill(skillDir, skillName) {
  const versions = detectVersions(skillDir);

  if (versions.length > 0) {
    const currentDir = versions[0].path;
    const skill = parseSkillFromDir(currentDir, skillName);
    if (!skill) return null;

    skill.currentVersion = versions[0].version;
    skill.versions = [
      ...versions.map((v) => ({ version: v.version, date: v.date })),
      { version: 'original', date: null },
    ];
    return skill;
  }

  const skill = parseSkillFromDir(skillDir, skillName);
  if (!skill) return null;

  skill.currentVersion = null;
  skill.versions = [];
  return skill;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run --config vitest.config.server.js server/__tests__/parser.test.js`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/parser.js server/__tests__/parser.test.js
git commit -m "feat: make parseSkill version-aware with parseSkillFromDir extraction"
```

---

### Task 3: API — Version endpoints

**Files:**
- Modify: `server/app.js`
- Test: `server/__tests__/api.test.js`

- [ ] **Step 1: Create versioned skill fixture for API tests**

Create a test fixture in `skill_repo/` for integration testing. Create the directory and files:

```bash
mkdir -p skill_repo/webapp-testing/20260331-version-test
```

Create `skill_repo/webapp-testing/20260331-version-test/SKILL.md`:

```markdown
---
name: webapp-testing
description: "Versioned webapp testing skill"
license: Complete terms in LICENSE.txt
---

Versioned content for webapp-testing.
```

Note: We use an existing skill (`webapp-testing`) so classifier still works. We'll remove this fixture after tests.

- [ ] **Step 2: Write failing tests for version endpoints**

Add to `server/__tests__/api.test.js`:

```js
describe('GET /api/skills/:name/versions', () => {
  it('should return versions list for versioned skill', async () => {
    const res = await request(app).get('/api/skills/webapp-testing/versions');
    expect(res.status).toBe(200);
    expect(res.body.skill).toBe('webapp-testing');
    expect(res.body.currentVersion).toBeDefined();
    expect(res.body.versions).toBeInstanceOf(Array);
    expect(res.body.versions.length).toBeGreaterThanOrEqual(2); // at least version + original
  });

  it('should return empty versions for unversioned skill', async () => {
    const res = await request(app).get('/api/skills/pdf/versions');
    expect(res.status).toBe(200);
    expect(res.body.currentVersion).toBeNull();
    expect(res.body.versions).toEqual([]);
  });

  it('should return 404 for unknown skill', async () => {
    const res = await request(app).get('/api/skills/nonexistent/versions');
    expect(res.status).toBe(404);
  });
});

describe('GET /api/skills/:name/versions/:version', () => {
  it('should return specific version data', async () => {
    const res = await request(app).get('/api/skills/webapp-testing/versions/20260331-version-test');
    expect(res.status).toBe(200);
    expect(res.body.name).toBe('webapp-testing');
    expect(res.body.content).toContain('Versioned content');
  });

  it('should return original version data', async () => {
    const res = await request(app).get('/api/skills/webapp-testing/versions/original');
    expect(res.status).toBe(200);
    expect(res.body.name).toBe('webapp-testing');
    expect(res.body.content).toBeDefined();
  });

  it('should return 404 for nonexistent version', async () => {
    const res = await request(app).get('/api/skills/webapp-testing/versions/99990101-fake');
    expect(res.status).toBe(404);
  });

  it('should return 404 for unknown skill', async () => {
    const res = await request(app).get('/api/skills/nonexistent/versions/original');
    expect(res.status).toBe(404);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npx vitest run --config vitest.config.server.js server/__tests__/api.test.js`
Expected: FAIL — routes not defined (404)

- [ ] **Step 4: Implement version endpoints in app.js**

Add imports at the top of `server/app.js`:

```js
import { parseSkillFromDir } from './parser.js';
```

Add helper function inside `createApp`:

```js
function resolveVersionDir(skillRepoPath, skillName, version) {
  if (version === 'original') {
    return resolve(skillRepoPath, skillName);
  }
  return resolve(skillRepoPath, skillName, version);
}
```

Add version endpoints after existing routes (before the production static files block):

```js
// List versions for a skill
app.get('/api/skills/:name/versions', (req, res) => {
  const skill = getSkills().get(req.params.name);
  if (!skill) {
    return res.status(404).json({ error: `Skill not found: ${req.params.name}` });
  }
  res.json({
    skill: req.params.name,
    currentVersion: skill.currentVersion,
    versions: skill.versions,
  });
});

// Get specific version of a skill
app.get('/api/skills/:name/versions/:version', (req, res) => {
  const skill = getSkills().get(req.params.name);
  if (!skill) {
    return res.status(404).json({ error: `Skill not found: ${req.params.name}` });
  }

  const { version } = req.params;
  const validVersions = skill.versions.map((v) => v.version);
  if (skill.currentVersion === null && version !== 'original') {
    return res.status(404).json({ error: `Version not found: ${version}` });
  }
  if (skill.currentVersion !== null && !validVersions.includes(version)) {
    return res.status(404).json({ error: `Version not found: ${version}` });
  }

  const versionDir = resolveVersionDir(skillRepoPath, req.params.name, version);
  const versionSkill = parseSkillFromDir(versionDir, req.params.name);
  if (!versionSkill) {
    return res.status(404).json({ error: `Version not found: ${version}` });
  }

  res.json({
    ...versionSkill,
    installPaths: {
      claudeCode: `~/.claude/skills/${versionSkill.name}`,
      opencode: `~/.opencode/skills/${versionSkill.name}`,
    },
    repoPath: versionDir,
  });
});
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npx vitest run --config vitest.config.server.js server/__tests__/api.test.js`
Expected: All tests PASS

- [ ] **Step 6: Update existing API test expectations**

The existing test `should include required fields on each skill` should also check for new fields. Add to the test:

```js
expect(skill).toHaveProperty('currentVersion');
expect(skill).toHaveProperty('versions');
```

The skill list endpoint now strips `content` but keeps `currentVersion` and `versions`. Verify the list endpoint still works with:

Run: `npx vitest run --config vitest.config.server.js server/__tests__/api.test.js`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add server/app.js server/__tests__/api.test.js
git commit -m "feat: add version list and version detail API endpoints"
```

---

### Task 4: API — Version ZIP and files endpoints

**Files:**
- Modify: `server/app.js`
- Modify: `server/zipper.js`
- Modify: `server/fileReader.js`
- Test: `server/__tests__/api.test.js`

- [ ] **Step 1: Write failing tests for version ZIP and files**

Add to `server/__tests__/api.test.js`:

```js
describe('GET /api/skills/:name/versions/:version/zip', () => {
  it('should return a ZIP for a specific version', async () => {
    const res = await request(app).get('/api/skills/webapp-testing/versions/20260331-version-test/zip');
    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toBe('application/zip');
  });

  it('should return ZIP for original version', async () => {
    const res = await request(app).get('/api/skills/webapp-testing/versions/original/zip');
    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toBe('application/zip');
  });

  it('should return 404 for nonexistent version ZIP', async () => {
    const res = await request(app).get('/api/skills/webapp-testing/versions/99990101-fake/zip');
    expect(res.status).toBe(404);
  });
});

describe('GET /api/skills/:name/versions/:version/files', () => {
  it('should return files for a specific version', async () => {
    const res = await request(app).get('/api/skills/webapp-testing/versions/20260331-version-test/files');
    expect(res.status).toBe(200);
    expect(res.body).toBeInstanceOf(Array);
    const paths = res.body.map((f) => f.path);
    expect(paths).toContain('SKILL.md');
  });

  it('should return 404 for nonexistent version files', async () => {
    const res = await request(app).get('/api/skills/webapp-testing/versions/99990101-fake/files');
    expect(res.status).toBe(404);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run --config vitest.config.server.js server/__tests__/api.test.js`
Expected: FAIL — routes not defined

- [ ] **Step 3: Update `sendZip` in zipper.js**

Replace the existing `sendZip` function in `server/zipper.js`:

```js
import archiver from 'archiver';
import { existsSync } from 'fs';

export function sendZip(res, dirPath, zipName) {
  if (!existsSync(dirPath)) {
    res.status(404).json({ error: `Directory not found: ${dirPath}` });
    return;
  }

  res.set({
    'Content-Type': 'application/zip',
    'Content-Disposition': `attachment; filename="${zipName}.zip"`,
  });

  const archive = archiver('zip', { zlib: { level: 9 } });

  archive.on('error', (err) => {
    res.status(500).json({ error: err.message });
  });

  archive.pipe(res);
  archive.directory(dirPath, zipName);
  archive.finalize();
}
```

- [ ] **Step 4: Update `readSkillFiles` in fileReader.js**

Change the `readSkillFiles` function signature in `server/fileReader.js` to accept a direct directory path:

```js
export function readSkillFiles(dirPath) {
  if (!existsSync(dirPath)) return [];

  const results = [];
  collectFiles(dirPath, dirPath, results);

  results.sort((a, b) => {
    if (a.path === 'SKILL.md') return -1;
    if (b.path === 'SKILL.md') return 1;
    return a.path.localeCompare(b.path);
  });

  return results;
}
```

- [ ] **Step 5: Update existing callers in app.js**

Update the existing `/api/skills/:name/zip` route:

```js
app.get('/api/skills/:name/zip', (req, res) => {
  const skillDir = resolve(skillRepoPath, req.params.name);
  const skill = getSkills().get(req.params.name);
  if (!skill) {
    return res.status(404).json({ error: `Skill not found: ${req.params.name}` });
  }
  const currentDir = skill.currentVersion
    ? resolve(skillRepoPath, req.params.name, skill.currentVersion)
    : resolve(skillRepoPath, req.params.name);
  sendZip(res, currentDir, req.params.name);
});
```

Update the existing `/api/skills/:name/files` route:

```js
app.get('/api/skills/:name/files', (req, res) => {
  const skill = getSkills().get(req.params.name);
  if (!skill) {
    return res.status(404).json({ error: `Skill not found: ${req.params.name}` });
  }
  const currentDir = skill.currentVersion
    ? resolve(skillRepoPath, req.params.name, skill.currentVersion)
    : resolve(skillRepoPath, req.params.name);
  const files = readSkillFiles(currentDir);
  res.json(files);
});
```

Add the new version ZIP and files endpoints:

```js
// Download specific version as ZIP
app.get('/api/skills/:name/versions/:version/zip', (req, res) => {
  const skill = getSkills().get(req.params.name);
  if (!skill) {
    return res.status(404).json({ error: `Skill not found: ${req.params.name}` });
  }

  const { version } = req.params;
  const validVersions = skill.versions.map((v) => v.version);
  if (skill.currentVersion !== null && !validVersions.includes(version)) {
    return res.status(404).json({ error: `Version not found: ${version}` });
  }

  const versionDir = resolveVersionDir(skillRepoPath, req.params.name, version);
  sendZip(res, versionDir, `${req.params.name}-${version}`);
});

// List files in specific version
app.get('/api/skills/:name/versions/:version/files', (req, res) => {
  const skill = getSkills().get(req.params.name);
  if (!skill) {
    return res.status(404).json({ error: `Skill not found: ${req.params.name}` });
  }

  const { version } = req.params;
  const validVersions = skill.versions.map((v) => v.version);
  if (skill.currentVersion !== null && !validVersions.includes(version)) {
    return res.status(404).json({ error: `Version not found: ${version}` });
  }

  const versionDir = resolveVersionDir(skillRepoPath, req.params.name, version);
  if (!existsSync(versionDir)) {
    return res.status(404).json({ error: `Version not found: ${version}` });
  }
  const files = readSkillFiles(versionDir);
  res.json(files);
});
```

Add `existsSync` import at the top of `app.js` (already imported, just verify).

- [ ] **Step 6: Run all server tests**

Run: `npx vitest run --config vitest.config.server.js`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add server/app.js server/zipper.js server/fileReader.js server/__tests__/api.test.js
git commit -m "feat: add version ZIP/files endpoints, update zipper and fileReader signatures"
```

---

### Task 5: Frontend — Version hooks

**Files:**
- Modify: `client/src/hooks/useSkills.js`
- Test: `client/src/hooks/useSkills.test.js`

- [ ] **Step 1: Read existing useSkills tests**

Read `client/src/hooks/useSkills.test.js` to understand the test pattern used.

- [ ] **Step 2: Write failing tests for version hooks**

Add to `client/src/hooks/useSkills.test.js`:

```js
describe('useSkillVersion', () => {
  it('should fetch specific version data', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        name: 'test-skill',
        description: 'Version 1',
        content: 'v1 content',
      }),
    });

    const { result } = renderHook(() => useSkillVersion('test-skill', '20260401-v1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.skill.description).toBe('Version 1');
    expect(global.fetch).toHaveBeenCalledWith('/api/skills/test-skill/versions/20260401-v1');
  });

  it('should not fetch when version is null', async () => {
    global.fetch = vi.fn();
    const { result } = renderHook(() => useSkillVersion('test-skill', null));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
```

Import `useSkillVersion` from the hooks file.

- [ ] **Step 3: Run tests to verify they fail**

Run: `npx vitest run --config client/vitest.config.js client/src/hooks/useSkills.test.js` (or from client dir: `npx vitest run src/hooks/useSkills.test.js`)
Expected: FAIL — `useSkillVersion` not exported

- [ ] **Step 4: Implement `useSkillVersion` hook**

Add to `client/src/hooks/useSkills.js`:

```js
export function useSkillVersion(name, version) {
  const [skill, setSkill] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!name || !version) return;

    setLoading(true);
    fetch(`/api/skills/${name}/versions/${version}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setSkill(data);
        setError(null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [name, version]);

  return { skill, loading, error };
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npx vitest run` (from client dir)
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add client/src/hooks/useSkills.js client/src/hooks/useSkills.test.js
git commit -m "feat: add useSkillVersion hook for fetching specific version data"
```

---

### Task 6: Frontend — Version selector in SkillDetail

**Files:**
- Modify: `client/src/components/SkillDetail.jsx`
- Modify: `client/src/pages/SkillPage.jsx`

- [ ] **Step 1: Add version selector component to SkillDetail.jsx**

Add `useState` to the existing import in `client/src/components/SkillDetail.jsx`:

```js
import { useState } from 'react';
```

Add `useSkillVersion` import:

```js
import { useSkillVersion } from '../hooks/useSkills';
```

Add version state and hook at the top of the `SkillDetail` component function, before `badge`:

```js
export default function SkillDetail({ skill }) {
  const [selectedVersion, setSelectedVersion] = useState(null);
  const { skill: versionSkill, loading: versionLoading } = useSkillVersion(
    skill.name,
    selectedVersion
  );

  // Use version data if a non-current version is selected, otherwise use default skill data
  const displaySkill = versionSkill || skill;
  const badge = BADGE_STYLES[displaySkill.category] || BADGE_STYLES.Other;
```

Update `handleDownload` to use the selected version:

```js
const handleDownload = () => {
  if (selectedVersion) {
    window.open(`/api/skills/${skill.name}/versions/${selectedVersion}/zip`, '_blank');
  } else {
    window.open(`/api/skills/${skill.name}/zip`, '_blank');
  }
};
```

Add the version selector JSX after the hero header div (before the two-column layout div), only when `skill.versions.length > 0`:

```jsx
{/* Version Selector */}
{skill.versions && skill.versions.length > 0 && (
  <div
    className="rounded-xl p-4 mb-6 flex items-center gap-3"
    style={{
      backgroundColor: 'var(--bg-secondary)',
      border: '1px solid var(--border)',
    }}
  >
    <label
      className="text-sm font-medium shrink-0"
      style={{ color: 'var(--text-primary)' }}
      htmlFor="version-select"
    >
      Version
    </label>
    <select
      id="version-select"
      value={selectedVersion || ''}
      onChange={(e) => setSelectedVersion(e.target.value || null)}
      className="flex-1 text-sm rounded-lg px-3 py-2 outline-none"
      style={{
        backgroundColor: 'var(--bg-primary)',
        color: 'var(--text-primary)',
        border: '1px solid var(--border)',
      }}
    >
      <option value="">
        {skill.currentVersion} (latest)
      </option>
      {skill.versions
        .filter((v) => v.version !== skill.currentVersion)
        .map((v) => (
          <option key={v.version} value={v.version}>
            {v.version}
          </option>
        ))}
    </select>
    {versionLoading && (
      <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
        Loading...
      </span>
    )}
  </div>
)}
```

- [ ] **Step 2: Update all references in SkillDetail to use `displaySkill`**

Replace `skill.description` with `displaySkill.description` in the hero header description paragraph.

Replace `skill.name` in the h1 with `displaySkill.name` (though name won't change).

Update the InstallCommands component to pass `displaySkill`:

```jsx
<InstallCommands skill={displaySkill} />
```

Update the SkillFiles component to pass version info:

```jsx
<SkillFiles
  name={skill.name}
  version={selectedVersion}
/>
```

Update sidebar stat values to use `displaySkill`:

```jsx
{displaySkill.fileCount} files
```

```jsx
{displaySkill.license}
```

```jsx
{new Date(displaySkill.lastUpdated).toLocaleDateString()}
```

- [ ] **Step 3: Update SkillFiles to accept version prop**

In `client/src/components/SkillFiles.jsx`, update the component to accept and use version:

```jsx
export default function SkillFiles({ name, version }) {
  const filesUrl = version
    ? `/api/skills/${name}/versions/${version}/files`
    : `/api/skills/${name}/files`;
```

Update the `useSkillFiles` call — instead of using the hook directly, fetch inline or update the hook. The simplest approach: update `useSkillFiles` to accept an optional URL override.

Actually, the cleaner approach is to update `useSkillFiles` in `useSkills.js` to accept an optional version:

```js
export function useSkillFiles(name, version) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!name) return;

    const url = version
      ? `/api/skills/${name}/versions/${version}/files`
      : `/api/skills/${name}/files`;

    setLoading(true);
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setFiles(data);
        setError(null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [name, version]);

  return { files, loading, error };
}
```

Then in `SkillFiles.jsx`:

```jsx
export default function SkillFiles({ name, version }) {
  const { files, loading, error } = useSkillFiles(name, version);
```

- [ ] **Step 4: Run dev server and manually verify**

Run: `node manage.js dev`

1. Navigate to an unversioned skill — no version selector shown
2. Create a test version directory in `skill_repo/webapp-testing/20260331-version-test/` with a `SKILL.md`
3. Navigate to webapp-testing skill page — version selector should appear
4. Switch versions — content, install commands, and sidebar stats should update

- [ ] **Step 5: Commit**

```bash
git add client/src/components/SkillDetail.jsx client/src/components/SkillFiles.jsx client/src/hooks/useSkills.js client/src/pages/SkillPage.jsx
git commit -m "feat: add version selector UI in skill detail page"
```

---

### Task 7: Cleanup and final verification

**Files:**
- Remove test fixture: `skill_repo/webapp-testing/20260331-version-test/`

- [ ] **Step 1: Remove test fixture**

```bash
rm -rf skill_repo/webapp-testing/20260331-version-test
```

- [ ] **Step 2: Run all server tests**

Run: `npx vitest run --config vitest.config.server.js`
Expected: All tests PASS (API tests that rely on the fixture will need the fixture re-created in a `beforeAll` or the tests updated to use a separate fixture directory)

Note: If API tests fail because the fixture is gone, update `server/__tests__/api.test.js` to create/cleanup the fixture in `beforeAll`/`afterAll`:

```js
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'fs';

const VERSION_FIXTURE = resolve(SKILL_REPO_PATH, 'webapp-testing', '20260331-version-test');

beforeAll(async () => {
  // Create version fixture
  mkdirSync(VERSION_FIXTURE, { recursive: true });
  writeFileSync(
    resolve(VERSION_FIXTURE, 'SKILL.md'),
    `---
name: webapp-testing
description: "Versioned webapp testing skill"
license: Complete terms in LICENSE.txt
---

Versioned content for webapp-testing.
`
  );

  watcher = initWatcher(SKILL_REPO_PATH);
  app = createApp(SKILL_REPO_PATH);
});

afterAll(async () => {
  if (watcher) await watcher.close();
  if (existsSync(VERSION_FIXTURE)) {
    rmSync(VERSION_FIXTURE, { recursive: true, force: true });
  }
});
```

- [ ] **Step 3: Run all client tests**

Run: `cd client && npx vitest run`
Expected: All tests PASS

- [ ] **Step 4: Run full test suite**

Run: `node manage.js test`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/__tests__/api.test.js
git commit -m "test: use beforeAll/afterAll fixtures for version API tests"
```
