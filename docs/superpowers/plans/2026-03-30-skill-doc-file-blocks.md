# Skill Document File Blocks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-markdown documentation block in the skill detail view with a flat list of per-file blocks — one block per file in the skill directory, rendered as markdown or code depending on file type.

**Architecture:** A new `GET /api/skills/:name/files` endpoint reads all non-binary files recursively from the skill directory and returns `[{ path, content, language }]`. The frontend fetches this via a new `useSkillFiles` hook and renders file blocks through a new `SkillFiles` component that replaces the existing Documentation section in `SkillDetail`.

**Tech Stack:** Node.js (ESM), Express, React 18, Vitest, Supertest, React Testing Library, ReactMarkdown + remark-gfm

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `server/fileReader.js` | Create | Recursively read files, infer language, detect binary, enforce 500 KB limit |
| `server/app.js` | Modify | Add `/api/skills/:name/files` endpoint |
| `server/__tests__/files-endpoint.test.js` | Create | Integration tests for the new endpoint |
| `client/src/hooks/useSkills.js` | Modify | Add `useSkillFiles(name)` hook |
| `client/src/hooks/useSkills.test.js` | Modify | Add tests for `useSkillFiles` |
| `client/src/test/mocks.js` | Modify | Add `mockSkillFiles` and update `setupFetchMock` |
| `client/src/components/SkillFiles.jsx` | Create | Renders flat list of file blocks (markdown or code) |
| `client/src/components/SkillFiles.test.jsx` | Create | Unit tests for SkillFiles component |
| `client/src/components/SkillDetail.jsx` | Modify | Replace Documentation section with `<SkillFiles name={skill.name} />` |
| `client/src/components/SkillDetail.test.jsx` | Modify | Update docs-section test to expect file blocks instead of raw markdown |

---

## Task 1: Create `server/fileReader.js`

**Files:**
- Create: `server/fileReader.js`

- [ ] **Step 1: Write the failing test**

Create `server/__tests__/files-endpoint.test.js` with just the import check for now:

```js
import { describe, it, expect } from 'vitest';
import { readSkillFiles, inferLanguage } from '../fileReader.js';
import { resolve } from 'path';

const SKILL_REPO_PATH = resolve(import.meta.dirname, '..', '..', 'skill_repo');

describe('inferLanguage', () => {
  it('returns markdown for .md files', () => {
    expect(inferLanguage('SKILL.md')).toBe('markdown');
    expect(inferLanguage('shared/models.md')).toBe('markdown');
  });

  it('returns python for .py files', () => {
    expect(inferLanguage('example.py')).toBe('python');
  });

  it('returns typescript for .ts and .tsx files', () => {
    expect(inferLanguage('app.ts')).toBe('typescript');
    expect(inferLanguage('App.tsx')).toBe('typescript');
  });

  it('returns javascript for .js and .jsx files', () => {
    expect(inferLanguage('index.js')).toBe('javascript');
    expect(inferLanguage('App.jsx')).toBe('javascript');
  });

  it('returns text for unknown extensions', () => {
    expect(inferLanguage('LICENSE.txt')).toBe('text');
    expect(inferLanguage('README')).toBe('text');
  });

  it('returns json for .json files', () => {
    expect(inferLanguage('config.json')).toBe('json');
  });

  it('returns yaml for .yaml and .yml files', () => {
    expect(inferLanguage('config.yaml')).toBe('yaml');
    expect(inferLanguage('config.yml')).toBe('yaml');
  });
});

describe('readSkillFiles', () => {
  it('returns an array for a known skill', () => {
    const files = readSkillFiles(SKILL_REPO_PATH, 'brand-guidelines');
    expect(Array.isArray(files)).toBe(true);
    expect(files.length).toBeGreaterThan(0);
  });

  it('puts SKILL.md first', () => {
    const files = readSkillFiles(SKILL_REPO_PATH, 'brand-guidelines');
    expect(files[0].path).toBe('SKILL.md');
  });

  it('each file has path, content, and language fields', () => {
    const files = readSkillFiles(SKILL_REPO_PATH, 'brand-guidelines');
    files.forEach((f) => {
      expect(f).toHaveProperty('path');
      expect(f).toHaveProperty('content');
      expect(f).toHaveProperty('language');
    });
  });

  it('returns empty array for unknown skill', () => {
    const files = readSkillFiles(SKILL_REPO_PATH, 'nonexistent-skill-xyz');
    expect(files).toEqual([]);
  });

  it('marks large files as truncated', () => {
    // brand-guidelines has small files, so none should be truncated
    const files = readSkillFiles(SKILL_REPO_PATH, 'brand-guidelines');
    const truncated = files.filter((f) => f.truncated);
    expect(truncated.length).toBe(0);
  });

  it('includes all files for skill with subdirectories', () => {
    const files = readSkillFiles(SKILL_REPO_PATH, 'claude-api');
    const paths = files.map((f) => f.path);
    expect(paths).toContain('SKILL.md');
    // Should include files from subdirectories
    const hasSubdirFiles = paths.some((p) => p.includes('/'));
    expect(hasSubdirFiles).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node manage.js test server`
Expected: FAIL — "Cannot find module '../fileReader.js'"

- [ ] **Step 3: Create `server/fileReader.js`**

```js
import { readFileSync, readdirSync, statSync, existsSync } from 'fs';
import { join, relative, extname } from 'path';

const MAX_FILE_SIZE = 500 * 1024; // 500 KB

const LANGUAGE_MAP = {
  '.md': 'markdown',
  '.py': 'python',
  '.ts': 'typescript',
  '.tsx': 'typescript',
  '.js': 'javascript',
  '.jsx': 'javascript',
  '.go': 'go',
  '.rb': 'ruby',
  '.java': 'java',
  '.cs': 'csharp',
  '.php': 'php',
  '.sh': 'bash',
  '.json': 'json',
  '.yaml': 'yaml',
  '.yml': 'yaml',
};

export function inferLanguage(filePath) {
  const ext = extname(filePath).toLowerCase();
  return LANGUAGE_MAP[ext] || 'text';
}

function isBinary(buffer) {
  const checkLength = Math.min(buffer.length, 8192);
  for (let i = 0; i < checkLength; i++) {
    if (buffer[i] === 0) return true;
  }
  return false;
}

function collectFiles(dir, baseDir, results) {
  const entries = readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      collectFiles(fullPath, baseDir, results);
    } else if (entry.isFile()) {
      const relPath = relative(baseDir, fullPath).replace(/\\/g, '/');
      const stat = statSync(fullPath);
      if (stat.size > MAX_FILE_SIZE) {
        results.push({ path: relPath, content: null, language: inferLanguage(relPath), truncated: true });
        continue;
      }
      const buffer = readFileSync(fullPath);
      if (isBinary(buffer)) continue;
      results.push({
        path: relPath,
        content: buffer.toString('utf-8'),
        language: inferLanguage(relPath),
      });
    }
  }
}

export function readSkillFiles(skillRepoPath, skillName) {
  const skillDir = join(skillRepoPath, skillName);
  if (!existsSync(skillDir)) return [];

  const results = [];
  collectFiles(skillDir, skillDir, results);

  // Sort: SKILL.md first, then alphabetically
  results.sort((a, b) => {
    if (a.path === 'SKILL.md') return -1;
    if (b.path === 'SKILL.md') return 1;
    return a.path.localeCompare(b.path);
  });

  return results;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node manage.js test server`
Expected: all new `inferLanguage` and `readSkillFiles` tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/fileReader.js server/__tests__/files-endpoint.test.js
git commit -m "feat: add fileReader module with language inference and recursive file reading"
```

---

## Task 2: Add `/api/skills/:name/files` endpoint

**Files:**
- Modify: `server/app.js`
- Modify: `server/__tests__/files-endpoint.test.js`

- [ ] **Step 1: Write the failing tests for the endpoint**

In `server/__tests__/files-endpoint.test.js`, add these imports at the **top of the file** (after the existing imports):

```js
import request from 'supertest';
import { initWatcher } from '../watcher.js';
import { createApp } from '../app.js';
```

Add these lifecycle hooks and describe block at the **bottom of the file**:

```js
let app;
let watcher;

beforeAll(async () => {
  watcher = initWatcher(SKILL_REPO_PATH);
  app = createApp(SKILL_REPO_PATH);
});

afterAll(async () => {
  if (watcher) await watcher.close();
});

describe('GET /api/skills/:name/files', () => {
  it('returns 200 with an array for a known skill', async () => {
    const res = await request(app).get('/api/skills/brand-guidelines/files');
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    expect(res.body.length).toBeGreaterThan(0);
  });

  it('returns SKILL.md as the first entry', async () => {
    const res = await request(app).get('/api/skills/brand-guidelines/files');
    expect(res.body[0].path).toBe('SKILL.md');
  });

  it('each entry has path, content, and language', async () => {
    const res = await request(app).get('/api/skills/brand-guidelines/files');
    res.body.forEach((f) => {
      expect(f).toHaveProperty('path');
      expect(f).toHaveProperty('content');
      expect(f).toHaveProperty('language');
    });
  });

  it('returns 404 for unknown skill', async () => {
    const res = await request(app).get('/api/skills/nonexistent-skill-xyz/files');
    expect(res.status).toBe(404);
    expect(res.body.error).toContain('nonexistent-skill-xyz');
  });

  it('includes files from subdirectories for claude-api', async () => {
    const res = await request(app).get('/api/skills/claude-api/files');
    expect(res.status).toBe(200);
    const paths = res.body.map((f) => f.path);
    const hasSubdir = paths.some((p) => p.includes('/'));
    expect(hasSubdir).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node manage.js test server`
Expected: FAIL — "expected 404 to equal 200" (endpoint not yet registered)

- [ ] **Step 3: Add the endpoint to `server/app.js`**

Add this import at the top of `server/app.js` (after existing imports):

```js
import { readSkillFiles } from './fileReader.js';
```

Add this route inside `createApp`, after the existing `/api/skills/:name` route (before the production static serving block):

```js
// List all files in a skill
app.get('/api/skills/:name/files', (req, res) => {
  const skill = getSkills().get(req.params.name);
  if (!skill) {
    return res.status(404).json({ error: `Skill not found: ${req.params.name}` });
  }
  const files = readSkillFiles(skillRepoPath, req.params.name);
  res.json(files);
});
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node manage.js test server`
Expected: all server tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/app.js server/__tests__/files-endpoint.test.js
git commit -m "feat: add GET /api/skills/:name/files endpoint"
```

---

## Task 3: Add `useSkillFiles` hook

**Files:**
- Modify: `client/src/hooks/useSkills.js`
- Modify: `client/src/hooks/useSkills.test.js`
- Modify: `client/src/test/mocks.js`

- [ ] **Step 1: Add mock data and update `setupFetchMock`**

In `client/src/test/mocks.js`, add after `mockSkillDetail`:

```js
export const mockSkillFiles = [
  { path: 'SKILL.md', content: '# Frontend Design\n\nThis is the skill content.\n\n## Usage\n\nUse it to build UIs.', language: 'markdown' },
  { path: 'LICENSE.txt', content: 'MIT License\n\nCopyright (c) 2024', language: 'text' },
  { path: 'templates/example.js', content: 'export default function() {}', language: 'javascript' },
];
```

Update `setupFetchMock` to include the files route:

```js
export function setupFetchMock(overrides = {}) {
  const defaultResponses = {
    '/api/skills': { skills: mockSkills, categories: mockCategories },
    '/api/skills/frontend-design': mockSkillDetail,
    '/api/skills/frontend-design/files': mockSkillFiles,
  };
  const responses = { ...defaultResponses, ...overrides };

  global.fetch = vi.fn((url) => {
    const path = url.split('?')[0];
    const data = responses[path];
    if (data) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(data),
      });
    }
    return Promise.resolve({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: 'Not found' }),
    });
  });
}
```

- [ ] **Step 2: Write the failing tests for `useSkillFiles`**

Add to the bottom of `client/src/hooks/useSkills.test.js`:

```js
import { mockSkillFiles } from '../test/mocks';

describe('useSkillFiles', () => {
  it('should fetch and return skill files', async () => {
    const { result } = renderHook(() => useSkillFiles('frontend-design'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.files).toEqual(mockSkillFiles);
    expect(result.current.error).toBeNull();
  });

  it('should start in loading state', () => {
    const { result } = renderHook(() => useSkillFiles('frontend-design'));
    expect(result.current.loading).toBe(true);
  });

  it('should not fetch when name is empty', () => {
    renderHook(() => useSkillFiles(''));
    expect(fetch).not.toHaveBeenCalled();
  });

  it('should handle 404 error', async () => {
    const { result } = renderHook(() => useSkillFiles('nonexistent'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('HTTP 404');
    expect(result.current.files).toEqual([]);
  });

  it('should handle network errors', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('Timeout')));
    const { result } = renderHook(() => useSkillFiles('frontend-design'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Timeout');
  });

  it('should re-fetch when name changes', async () => {
    const { result, rerender } = renderHook(
      ({ name }) => useSkillFiles(name),
      { initialProps: { name: 'frontend-design' } }
    );
    await waitFor(() => expect(result.current.loading).toBe(false));

    rerender({ name: 'pdf' });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
```

Also add `useSkillFiles` to the import at the top of the test file:

```js
import { useSkills, useSkillDetail, useSkillFiles } from './useSkills';
```

- [ ] **Step 3: Run test to verify it fails**

Run: `node manage.js test client`
Expected: FAIL — "useSkillFiles is not a function"

- [ ] **Step 4: Add `useSkillFiles` to `client/src/hooks/useSkills.js`**

Append to the end of `client/src/hooks/useSkills.js`:

```js
export function useSkillFiles(name) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!name) return;

    setLoading(true);
    fetch(`/api/skills/${name}/files`)
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
  }, [name]);

  return { files, loading, error };
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `node manage.js test client`
Expected: all client tests PASS

- [ ] **Step 6: Commit**

```bash
git add client/src/hooks/useSkills.js client/src/hooks/useSkills.test.js client/src/test/mocks.js
git commit -m "feat: add useSkillFiles hook"
```

---

## Task 4: Create `SkillFiles` component

**Files:**
- Create: `client/src/components/SkillFiles.jsx`
- Create: `client/src/components/SkillFiles.test.jsx`

- [ ] **Step 1: Write the failing tests**

Create `client/src/components/SkillFiles.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../test/render';
import SkillFiles from './SkillFiles';
import { mockSkillFiles, setupFetchMock } from '../test/mocks';

beforeEach(() => {
  setupFetchMock();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('SkillFiles', () => {
  it('shows loading state initially', () => {
    renderWithProviders(<SkillFiles name="frontend-design" />);
    expect(screen.getByText('Loading files…')).toBeInTheDocument();
  });

  it('renders a block for each file after loading', async () => {
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    expect(screen.getByText('SKILL.md')).toBeInTheDocument();
    expect(screen.getByText('LICENSE.txt')).toBeInTheDocument();
    expect(screen.getByText('templates/example.js')).toBeInTheDocument();
  });

  it('renders markdown files with ReactMarkdown', async () => {
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    // ReactMarkdown renders the h1 from the SKILL.md content
    expect(screen.getByRole('heading', { name: 'Frontend Design' })).toBeInTheDocument();
  });

  it('renders non-markdown files as code blocks', async () => {
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    // LICENSE.txt content rendered verbatim
    expect(screen.getByText(/MIT License/)).toBeInTheDocument();
  });

  it('shows language badge on non-markdown files', async () => {
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    expect(screen.getByText('javascript')).toBeInTheDocument();
  });

  it('shows truncation notice for truncated files', async () => {
    setupFetchMock({
      '/api/skills/frontend-design/files': [
        { path: 'big-file.md', content: null, language: 'markdown', truncated: true },
      ],
    });
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    expect(screen.getByText('File too large to preview')).toBeInTheDocument();
  });

  it('shows error message on fetch failure', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('Network error')));
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    expect(screen.getByText(/Network error/)).toBeInTheDocument();
  });

  it('shows no-files notice when list is empty', async () => {
    setupFetchMock({ '/api/skills/frontend-design/files': [] });
    renderWithProviders(<SkillFiles name="frontend-design" />);
    await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());

    expect(screen.getByText('No files found')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node manage.js test client`
Expected: FAIL — "Cannot find module './SkillFiles'"

- [ ] **Step 3: Create `client/src/components/SkillFiles.jsx`**

```jsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSkillFiles } from '../hooks/useSkills';

export default function SkillFiles({ name }) {
  const { files, loading, error } = useSkillFiles(name);

  if (loading) {
    return (
      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
        Loading files…
      </p>
    );
  }

  if (error) {
    return (
      <p className="text-sm text-red-500">
        Failed to load files: {error}
      </p>
    );
  }

  if (files.length === 0) {
    return (
      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
        No files found
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {files.map((file) => (
        <div
          key={file.path}
          className="rounded-xl overflow-hidden"
          style={{ border: '1px solid var(--border)' }}
        >
          {/* File header */}
          <div
            className="flex items-center justify-between px-4 py-2"
            style={{ backgroundColor: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}
          >
            <span className="text-xs font-mono font-medium" style={{ color: 'var(--text-primary)' }}>
              {file.path}
            </span>
            {file.language !== 'markdown' && (
              <span
                className="text-[10px] px-2 py-0.5 rounded font-medium"
                style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
              >
                {file.language}
              </span>
            )}
          </div>

          {/* File body */}
          <div
            className="p-4"
            style={{ backgroundColor: 'var(--bg-primary)' }}
          >
            {file.truncated ? (
              <p className="text-xs italic" style={{ color: 'var(--text-secondary)' }}>
                File too large to preview
              </p>
            ) : file.language === 'markdown' ? (
              <div className="prose prose-sm max-w-none skill-markdown" style={{ color: 'var(--text-primary)' }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{file.content}</ReactMarkdown>
              </div>
            ) : (
              <pre
                className="text-xs overflow-x-auto"
                style={{ color: 'var(--text-primary)', margin: 0 }}
              >
                <code>{file.content}</code>
              </pre>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node manage.js test client`
Expected: all client tests PASS

- [ ] **Step 5: Commit**

```bash
git add client/src/components/SkillFiles.jsx client/src/components/SkillFiles.test.jsx
git commit -m "feat: add SkillFiles component with per-file blocks"
```

---

## Task 5: Wire `SkillFiles` into `SkillDetail`

**Files:**
- Modify: `client/src/components/SkillDetail.jsx`
- Modify: `client/src/components/SkillDetail.test.jsx`

- [ ] **Step 1: Update the failing test first**

In `client/src/components/SkillDetail.test.jsx`, replace the two tests that check for markdown content rendering:

Replace:
```js
it('should render markdown content', () => {
  renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
  // react-markdown renders the heading from content
  expect(screen.getByText('Frontend Design')).toBeInTheDocument();
  expect(screen.getByText('Usage')).toBeInTheDocument();
});
```

With:
```js
it('should render SkillFiles component in Documentation section', async () => {
  renderWithProviders(<SkillDetail skill={mockSkillDetail} />);
  await waitFor(() => expect(screen.queryByText('Loading files…')).not.toBeInTheDocument());
  // SKILL.md file block header is visible
  expect(screen.getByText('SKILL.md')).toBeInTheDocument();
});
```

Also add these imports at the top of `SkillDetail.test.jsx`:

```js
import { waitFor } from '@testing-library/react';
import { setupFetchMock } from '../test/mocks';
```

And add a `beforeEach`:

```js
beforeEach(() => {
  setupFetchMock();
});
```

- [ ] **Step 2: Run test to verify the new test fails**

Run: `node manage.js test client`
Expected: FAIL — "Unable to find an element with the text: SKILL.md"

- [ ] **Step 3: Update `SkillDetail.jsx` to use `SkillFiles`**

In `client/src/components/SkillDetail.jsx`:

Replace the import line for ReactMarkdown/remarkGfm at the top with:

```jsx
import SkillFiles from './SkillFiles';
```

(Remove `import ReactMarkdown from 'react-markdown';` and `import remarkGfm from 'remark-gfm';` — they are no longer used in this file.)

Replace the entire Documentation block (lines 82–107):

```jsx
{/* Documentation */}
<div>
  <h2
    className="text-sm font-semibold mb-3 flex items-center gap-2"
    style={{ color: 'var(--text-primary)' }}
  >
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
    Documentation
  </h2>
  <SkillFiles name={skill.name} />
</div>
```

- [ ] **Step 4: Run all tests**

Run: `node manage.js test`
Expected: all server and client tests PASS

- [ ] **Step 5: Commit**

```bash
git add client/src/components/SkillDetail.jsx client/src/components/SkillDetail.test.jsx
git commit -m "feat: replace documentation block with per-file SkillFiles view"
```
