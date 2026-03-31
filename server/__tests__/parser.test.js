import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'fs';
import { resolve } from 'path';
import { parseSkill, parseAllSkills, detectVersions } from '../parser.js';

const TEST_DIR = resolve(import.meta.dirname, '__fixtures__');

beforeAll(() => {
  // Create test fixture directories and files
  mkdirSync(resolve(TEST_DIR, 'valid-skill'), { recursive: true });
  mkdirSync(resolve(TEST_DIR, 'no-skill-md'), { recursive: true });
  mkdirSync(resolve(TEST_DIR, 'minimal-skill'), { recursive: true });
  mkdirSync(resolve(TEST_DIR, 'nested-skill', 'sub', 'deep'), { recursive: true });

  // Valid skill with full frontmatter
  writeFileSync(
    resolve(TEST_DIR, 'valid-skill', 'SKILL.md'),
    `---
name: valid-skill
description: "A test skill for validation"
license: MIT
---

# Valid Skill

This is the content of the skill.

## Usage

Use it for testing.
`
  );

  // Extra file in valid-skill
  writeFileSync(resolve(TEST_DIR, 'valid-skill', 'helper.js'), 'export default {}');

  // Minimal skill with no frontmatter values
  writeFileSync(
    resolve(TEST_DIR, 'minimal-skill', 'SKILL.md'),
    `---
---

Just content, no metadata.
`
  );

  // No SKILL.md directory
  writeFileSync(resolve(TEST_DIR, 'no-skill-md', 'README.md'), '# Not a skill');

  // Nested skill with subdirectories
  writeFileSync(
    resolve(TEST_DIR, 'nested-skill', 'SKILL.md'),
    `---
name: nested-skill
description: "Skill with nested files"
license: Apache-2.0
---

Nested skill content.
`
  );
  writeFileSync(resolve(TEST_DIR, 'nested-skill', 'index.js'), '');
  writeFileSync(resolve(TEST_DIR, 'nested-skill', 'sub', 'util.js'), '');
  writeFileSync(resolve(TEST_DIR, 'nested-skill', 'sub', 'deep', 'config.json'), '{}');

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
});

afterAll(() => {
  if (existsSync(TEST_DIR)) {
    rmSync(TEST_DIR, { recursive: true, force: true });
  }
});

describe('parser', () => {
  describe('parseSkill', () => {
    it('should parse a valid skill with full frontmatter', () => {
      const skill = parseSkill(resolve(TEST_DIR, 'valid-skill'), 'valid-skill');
      expect(skill).not.toBeNull();
      expect(skill.name).toBe('valid-skill');
      expect(skill.description).toBe('A test skill for validation');
      expect(skill.license).toBe('MIT');
      expect(skill.content).toContain('# Valid Skill');
      expect(skill.content).toContain('## Usage');
    });

    it('should include category and icon from classifier', () => {
      const skill = parseSkill(resolve(TEST_DIR, 'valid-skill'), 'valid-skill');
      expect(skill.category).toBeDefined();
      expect(skill.icon).toBeDefined();
    });

    it('should count files correctly', () => {
      const skill = parseSkill(resolve(TEST_DIR, 'valid-skill'), 'valid-skill');
      expect(skill.fileCount).toBe(2); // SKILL.md + helper.js
    });

    it('should count nested files recursively', () => {
      const skill = parseSkill(resolve(TEST_DIR, 'nested-skill'), 'nested-skill');
      expect(skill.fileCount).toBe(4); // SKILL.md + index.js + sub/util.js + sub/deep/config.json
    });

    it('should include lastUpdated as ISO string', () => {
      const skill = parseSkill(resolve(TEST_DIR, 'valid-skill'), 'valid-skill');
      expect(skill.lastUpdated).toMatch(/^\d{4}-\d{2}-\d{2}T/);
      expect(() => new Date(skill.lastUpdated)).not.toThrow();
    });

    it('should return null when SKILL.md does not exist', () => {
      const skill = parseSkill(resolve(TEST_DIR, 'no-skill-md'), 'no-skill-md');
      expect(skill).toBeNull();
    });

    it('should use fallback values for missing frontmatter fields', () => {
      const skill = parseSkill(resolve(TEST_DIR, 'minimal-skill'), 'minimal-skill');
      expect(skill).not.toBeNull();
      expect(skill.name).toBe('minimal-skill'); // falls back to dir name
      expect(skill.description).toBe('');
      expect(skill.license).toBe('Unknown');
    });

    it('should return null for non-existent directory', () => {
      const skill = parseSkill(resolve(TEST_DIR, 'does-not-exist'), 'does-not-exist');
      expect(skill).toBeNull();
    });

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
  });

  describe('parseAllSkills', () => {
    it('should parse all valid skills from a directory', () => {
      const skills = parseAllSkills(TEST_DIR);
      expect(skills).toBeInstanceOf(Map);
      // valid-skill, minimal-skill, nested-skill, versioned-skill (no-skill-md is skipped)
      expect(skills.size).toBe(4);
    });

    it('should include skills by directory name as key', () => {
      const skills = parseAllSkills(TEST_DIR);
      expect(skills.has('valid-skill')).toBe(true);
      expect(skills.has('minimal-skill')).toBe(true);
      expect(skills.has('nested-skill')).toBe(true);
      expect(skills.has('versioned-skill')).toBe(true);
    });

    it('should skip directories without SKILL.md', () => {
      const skills = parseAllSkills(TEST_DIR);
      expect(skills.has('no-skill-md')).toBe(false);
    });

    it('should return empty map for non-existent path', () => {
      const skills = parseAllSkills('/nonexistent/path');
      expect(skills).toBeInstanceOf(Map);
      expect(skills.size).toBe(0);
    });

    it('should parse the real skill_repo', () => {
      const repoPath = resolve(import.meta.dirname, '..', '..', 'skill_repo');
      if (existsSync(repoPath)) {
        const skills = parseAllSkills(repoPath);
        expect(skills.size).toBe(17);
        expect(skills.has('pdf')).toBe(true);
        expect(skills.has('claude-api')).toBe(true);
        expect(skills.has('frontend-design')).toBe(true);
      }
    });
  });

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
});
