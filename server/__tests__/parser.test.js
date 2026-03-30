import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'fs';
import { resolve } from 'path';
import { parseSkill, parseAllSkills } from '../parser.js';

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
  });

  describe('parseAllSkills', () => {
    it('should parse all valid skills from a directory', () => {
      const skills = parseAllSkills(TEST_DIR);
      expect(skills).toBeInstanceOf(Map);
      // valid-skill, minimal-skill, nested-skill (no-skill-md is skipped)
      expect(skills.size).toBe(3);
    });

    it('should include skills by directory name as key', () => {
      const skills = parseAllSkills(TEST_DIR);
      expect(skills.has('valid-skill')).toBe(true);
      expect(skills.has('minimal-skill')).toBe(true);
      expect(skills.has('nested-skill')).toBe(true);
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
});
