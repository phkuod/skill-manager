import { describe, it, expect, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import { readSkillFiles, inferLanguage } from '../fileReader.js';
import { resolve } from 'path';
import { writeFileSync, mkdirSync, rmSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import request from 'supertest';
import { initWatcher, getSkills } from '../watcher.js';
import { createApp } from '../app.js';

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

  it('returns go for .go files', () => {
    expect(inferLanguage('main.go')).toBe('go');
  });

  it('returns ruby for .rb files', () => {
    expect(inferLanguage('app.rb')).toBe('ruby');
  });

  it('returns java for .java files', () => {
    expect(inferLanguage('App.java')).toBe('java');
  });

  it('returns csharp for .cs files', () => {
    expect(inferLanguage('App.cs')).toBe('csharp');
  });

  it('returns php for .php files', () => {
    expect(inferLanguage('index.php')).toBe('php');
  });

  it('returns bash for .sh files', () => {
    expect(inferLanguage('run.sh')).toBe('bash');
  });
});

describe('readSkillFiles', () => {
  it('returns an array for a known skill', () => {
    const files = readSkillFiles(resolve(SKILL_REPO_PATH, 'brand-guidelines'));
    expect(Array.isArray(files)).toBe(true);
    expect(files.length).toBeGreaterThan(0);
  });

  it('puts SKILL.md first', () => {
    const files = readSkillFiles(resolve(SKILL_REPO_PATH, 'brand-guidelines'));
    expect(files[0].path).toBe('SKILL.md');
  });

  it('each file has path, content, and language fields', () => {
    const files = readSkillFiles(resolve(SKILL_REPO_PATH, 'brand-guidelines'));
    files.forEach((f) => {
      expect(f).toHaveProperty('path');
      expect(f).toHaveProperty('content');
      expect(f).toHaveProperty('language');
    });
  });

  it('returns empty array for unknown skill', () => {
    const files = readSkillFiles(resolve(SKILL_REPO_PATH, 'nonexistent-skill-xyz'));
    expect(files).toEqual([]);
  });

  it('includes all files for skill with subdirectories', () => {
    const files = readSkillFiles(resolve(SKILL_REPO_PATH, 'claude-api'));
    const paths = files.map((f) => f.path);
    expect(paths).toContain('SKILL.md');
    const hasSubdirFiles = paths.some((p) => p.includes('/'));
    expect(hasSubdirFiles).toBe(true);
  });
});

describe('readSkillFiles - truncation behavior', () => {
  let tmpSkillRepo;
  let tmpSkillDir;

  beforeEach(() => {
    tmpSkillRepo = join(tmpdir(), 'skill-test-' + Date.now());
    tmpSkillDir = join(tmpSkillRepo, 'test-skill');
    mkdirSync(tmpSkillDir, { recursive: true });
    // Write SKILL.md
    writeFileSync(join(tmpSkillDir, 'SKILL.md'), '# Test Skill\n');
  });

  afterEach(() => {
    rmSync(tmpSkillRepo, { recursive: true, force: true });
  });

  it('returns truncated:true and content:null for files over 500KB', () => {
    // Create a file > 500 KB
    const bigContent = 'x'.repeat(501 * 1024);
    writeFileSync(join(tmpSkillDir, 'bigfile.txt'), bigContent);

    const files = readSkillFiles(tmpSkillDir);
    const bigFile = files.find((f) => f.path === 'bigfile.txt');
    expect(bigFile).toBeDefined();
    expect(bigFile.truncated).toBe(true);
    expect(bigFile.content).toBeNull();
  });

  it('skips binary files containing null bytes', () => {
    // Create a binary file with null bytes
    const binaryBuffer = Buffer.alloc(100, 0); // all null bytes
    writeFileSync(join(tmpSkillDir, 'image.bin'), binaryBuffer);

    const files = readSkillFiles(tmpSkillDir);
    const binaryFile = files.find((f) => f.path === 'image.bin');
    expect(binaryFile).toBeUndefined();
  });

  it('includes non-binary files that pass size limit', () => {
    // Create a text file just under the limit
    const smallContent = 'This is a small text file\n'.repeat(100);
    writeFileSync(join(tmpSkillDir, 'smallfile.txt'), smallContent);

    const files = readSkillFiles(tmpSkillDir);
    const smallFile = files.find((f) => f.path === 'smallfile.txt');
    expect(smallFile).toBeDefined();
    expect(smallFile.content).toBeDefined();
    expect(smallFile.truncated).toBeUndefined();
  });
});

let app;
let watcher;

beforeAll(async () => {
  watcher = initWatcher(SKILL_REPO_PATH);
  app = createApp(SKILL_REPO_PATH, { getSkills });
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
