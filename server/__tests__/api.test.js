import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { resolve } from 'path';
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'fs';
import request from 'supertest';
import { initWatcher } from '../watcher.js';
import { createApp } from '../app.js';

const SKILL_REPO_PATH = resolve(import.meta.dirname, '..', '..', 'skill_repo');
const VERSION_FIXTURE = resolve(SKILL_REPO_PATH, 'webapp-testing', '20260331-version-test');
let app;
let watcher;

beforeAll(async () => {
  // Remove any stale fixture from a previous crashed run
  if (existsSync(VERSION_FIXTURE)) {
    rmSync(VERSION_FIXTURE, { recursive: true, force: true });
  }
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

describe('API', () => {
  describe('GET /api/health', () => {
    it('should return health status', async () => {
      const res = await request(app).get('/api/health');
      expect(res.status).toBe(200);
      expect(res.body.status).toBe('ok');
      expect(res.body.skillCount).toBe(17);
    });
  });

  describe('GET /api/skills', () => {
    it('should return all skills', async () => {
      const res = await request(app).get('/api/skills');
      expect(res.status).toBe(200);
      expect(res.body.skills).toBeInstanceOf(Array);
      expect(res.body.skills.length).toBe(17);
      expect(res.body.categories).toBeInstanceOf(Array);
      expect(res.body.categories[0]).toBe('All');
    });

    it('should not include content field in skill list', async () => {
      const res = await request(app).get('/api/skills');
      const skill = res.body.skills[0];
      expect(skill).not.toHaveProperty('content');
    });

    it('should include required fields on each skill', async () => {
      const res = await request(app).get('/api/skills');
      const skill = res.body.skills[0];
      expect(skill).toHaveProperty('name');
      expect(skill).toHaveProperty('description');
      expect(skill).toHaveProperty('category');
      expect(skill).toHaveProperty('icon');
      expect(skill).toHaveProperty('license');
      expect(skill).toHaveProperty('fileCount');
      expect(skill).toHaveProperty('lastUpdated');
      expect(skill).toHaveProperty('currentVersion');
      expect(skill).toHaveProperty('versions');
    });

    describe('search filter', () => {
      it('should filter by name', async () => {
        const res = await request(app).get('/api/skills?search=pdf');
        expect(res.status).toBe(200);
        const names = res.body.skills.map((s) => s.name);
        expect(names).toContain('pdf');
      });

      it('should filter by description', async () => {
        const res = await request(app).get('/api/skills?search=claude');
        expect(res.status).toBe(200);
        expect(res.body.skills.length).toBeGreaterThan(0);
      });

      it('should be case-insensitive', async () => {
        const resLower = await request(app).get('/api/skills?search=pdf');
        const resUpper = await request(app).get('/api/skills?search=PDF');
        expect(resLower.body.skills.length).toBe(resUpper.body.skills.length);
      });

      it('should return empty array for no matches', async () => {
        const res = await request(app).get('/api/skills?search=xyznonexistent');
        expect(res.status).toBe(200);
        expect(res.body.skills).toEqual([]);
      });

      it('should sort name matches before description matches', async () => {
        const res = await request(app).get('/api/skills?search=api');
        if (res.body.skills.length > 1) {
          const first = res.body.skills[0];
          expect(first.name.toLowerCase()).toContain('api');
        }
      });
    });

    describe('category filter', () => {
      it('should filter by category', async () => {
        const res = await request(app).get('/api/skills?category=Tools');
        expect(res.status).toBe(200);
        res.body.skills.forEach((s) => {
          expect(s.category).toBe('Tools');
        });
      });

      it('should return all skills for category=All', async () => {
        const res = await request(app).get('/api/skills?category=All');
        expect(res.body.skills.length).toBe(17);
      });

      it('should return empty for non-existent category', async () => {
        const res = await request(app).get('/api/skills?category=Nonexistent');
        expect(res.body.skills).toEqual([]);
      });

      it('should combine search and category filters', async () => {
        const res = await request(app).get('/api/skills?search=pdf&category=Tools');
        expect(res.status).toBe(200);
        res.body.skills.forEach((s) => {
          expect(s.category).toBe('Tools');
        });
        const names = res.body.skills.map((s) => s.name);
        expect(names).toContain('pdf');
      });
    });
  });

  describe('GET /api/skills/:name', () => {
    it('should return skill detail with content', async () => {
      const res = await request(app).get('/api/skills/pdf');
      expect(res.status).toBe(200);
      expect(res.body.name).toBe('pdf');
      expect(res.body.content).toBeDefined();
      expect(res.body.content.length).toBeGreaterThan(0);
    });

    it('should include install paths', async () => {
      const res = await request(app).get('/api/skills/pdf');
      expect(res.body.installPaths).toBeDefined();
      expect(res.body.installPaths.claudeCode).toBe('~/.claude/skills/pdf');
      expect(res.body.installPaths.opencode).toBe('~/.opencode/skills/pdf');
    });

    it('should include repo path', async () => {
      const res = await request(app).get('/api/skills/pdf');
      expect(res.body.repoPath).toContain('skill_repo');
      expect(res.body.repoPath).toContain('pdf');
    });

    it('should include all metadata fields', async () => {
      const res = await request(app).get('/api/skills/frontend-design');
      expect(res.body).toHaveProperty('name');
      expect(res.body).toHaveProperty('description');
      expect(res.body).toHaveProperty('category');
      expect(res.body).toHaveProperty('icon');
      expect(res.body).toHaveProperty('license');
      expect(res.body).toHaveProperty('fileCount');
      expect(res.body).toHaveProperty('lastUpdated');
      expect(res.body).toHaveProperty('content');
      expect(res.body).toHaveProperty('installPaths');
      expect(res.body).toHaveProperty('repoPath');
    });

    it('should return 404 for unknown skill', async () => {
      const res = await request(app).get('/api/skills/nonexistent');
      expect(res.status).toBe(404);
      expect(res.body.error).toContain('nonexistent');
    });
  });

  describe('GET /api/skills/:name/zip', () => {
    it('should return a ZIP file', async () => {
      const res = await request(app).get('/api/skills/brand-guidelines/zip');
      expect(res.status).toBe(200);
      expect(res.headers['content-type']).toBe('application/zip');
      expect(res.headers['content-disposition']).toContain('brand-guidelines.zip');
    });

    it('should return non-empty response body', async () => {
      const res = await request(app)
        .get('/api/skills/brand-guidelines/zip')
        .buffer(true)
        .parse((res, cb) => {
          const chunks = [];
          res.on('data', (chunk) => chunks.push(chunk));
          res.on('end', () => cb(null, Buffer.concat(chunks)));
        });
      expect(res.body.length).toBeGreaterThan(0);
    });

    it('should return 404 for unknown skill ZIP', async () => {
      const res = await request(app).get('/api/skills/nonexistent/zip');
      expect(res.status).toBe(404);
    });
  });

  describe('GET /api/skills/:name/versions', () => {
    it('should return versions list for versioned skill', async () => {
      const res = await request(app).get('/api/skills/webapp-testing/versions');
      expect(res.status).toBe(200);
      expect(res.body.skill).toBe('webapp-testing');
      expect(res.body.currentVersion).toBeDefined();
      expect(res.body.versions).toBeInstanceOf(Array);
      expect(res.body.versions.length).toBeGreaterThanOrEqual(2);
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

    it('should return 404 for original version on unversioned skill', async () => {
      const res = await request(app).get('/api/skills/pdf/versions/original');
      expect(res.status).toBe(404);
    });
  });
});
