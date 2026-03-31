import express from 'express';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';
import { getSkills } from './watcher.js';
import { getCategories } from './classifier.js';
import { sendZip } from './zipper.js';
import { readSkillFiles } from './fileReader.js';
import { parseSkillFromDir } from './parser.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(__dirname, '..');
const NODE_ENV = process.env.NODE_ENV || 'development';
const SKILL_REPO_PATH = process.env.SKILL_REPO_PATH || resolve(rootDir, 'skill_repo');

export function createApp(skillRepoPath = SKILL_REPO_PATH) {
  const app = express();

  function resolveVersionDir(skillName, version) {
    if (version === 'original') {
      return resolve(skillRepoPath, skillName);
    }
    return resolve(skillRepoPath, skillName, version);
  }

  function isValidVersion(skill, version) {
    if (skill.currentVersion === null) return false;
    return skill.versions.some((v) => v.version === version);
  }

  // Health check
  app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', environment: NODE_ENV, skillCount: getSkills().size });
  });

  // List all skills (with optional search and category filters)
  app.get('/api/skills', (req, res) => {
    const { search, category } = req.query;
    let results = Array.from(getSkills().values()).map(({ content, ...meta }) => meta);

    if (category && category !== 'All') {
      results = results.filter((s) => s.category === category);
    }

    if (search) {
      const term = search.toLowerCase();
      results = results.filter(
        (s) =>
          s.name.toLowerCase().includes(term) ||
          s.description.toLowerCase().includes(term)
      );
      // Sort: name matches first, then description matches
      results.sort((a, b) => {
        const aName = a.name.toLowerCase().includes(term) ? 0 : 1;
        const bName = b.name.toLowerCase().includes(term) ? 0 : 1;
        return aName - bName;
      });
    }

    res.json({ skills: results, categories: getCategories() });
  });

  // Skill detail (includes full markdown content)
  app.get('/api/skills/:name', (req, res) => {
    const skill = getSkills().get(req.params.name);
    if (!skill) {
      return res.status(404).json({ error: `Skill not found: ${req.params.name}` });
    }
    res.json({
      ...skill,
      installPaths: {
        claudeCode: `~/.claude/skills/${skill.name}`,
        opencode: `~/.opencode/skills/${skill.name}`,
      },
      repoPath: resolve(skillRepoPath, req.params.name),
    });
  });

  // Download skill as ZIP
  app.get('/api/skills/:name/zip', (req, res) => {
    const skill = getSkills().get(req.params.name);
    if (!skill) {
      return res.status(404).json({ error: `Skill not found: ${req.params.name}` });
    }
    const currentDir = skill.currentVersion
      ? resolve(skillRepoPath, req.params.name, skill.currentVersion)
      : resolve(skillRepoPath, req.params.name);
    sendZip(res, currentDir, req.params.name);
  });

  // List all files in a skill
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
    if (!isValidVersion(skill, version)) {
      return res.status(404).json({ error: `Version not found: ${version}` });
    }

    const versionDir = resolveVersionDir(req.params.name, version);
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

  // Download specific version as ZIP
  app.get('/api/skills/:name/versions/:version/zip', (req, res) => {
    const skill = getSkills().get(req.params.name);
    if (!skill) {
      return res.status(404).json({ error: `Skill not found: ${req.params.name}` });
    }

    const { version } = req.params;
    if (!isValidVersion(skill, version)) {
      return res.status(404).json({ error: `Version not found: ${version}` });
    }

    const versionDir = resolveVersionDir(req.params.name, version);
    sendZip(res, versionDir, `${req.params.name}-${version}`);
  });

  // List files in specific version
  app.get('/api/skills/:name/versions/:version/files', (req, res) => {
    const skill = getSkills().get(req.params.name);
    if (!skill) {
      return res.status(404).json({ error: `Skill not found: ${req.params.name}` });
    }

    const { version } = req.params;
    if (!isValidVersion(skill, version)) {
      return res.status(404).json({ error: `Version not found: ${version}` });
    }

    const versionDir = resolveVersionDir(req.params.name, version);
    const files = readSkillFiles(versionDir);
    res.json(files);
  });

  // In production, serve the built React app
  if (NODE_ENV === 'production') {
    const distPath = resolve(rootDir, 'client', 'dist');
    if (existsSync(distPath)) {
      app.use(express.static(distPath));
      app.get('*', (req, res) => {
        if (!req.path.startsWith('/api')) {
          res.sendFile(resolve(distPath, 'index.html'));
        }
      });
    }
  }

  return app;
}
