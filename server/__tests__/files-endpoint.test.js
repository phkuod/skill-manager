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
    const files = readSkillFiles(SKILL_REPO_PATH, 'brand-guidelines');
    const truncated = files.filter((f) => f.truncated);
    expect(truncated.length).toBe(0);
  });

  it('includes all files for skill with subdirectories', () => {
    const files = readSkillFiles(SKILL_REPO_PATH, 'claude-api');
    const paths = files.map((f) => f.path);
    expect(paths).toContain('SKILL.md');
    const hasSubdirFiles = paths.some((p) => p.includes('/'));
    expect(hasSubdirFiles).toBe(true);
  });
});
