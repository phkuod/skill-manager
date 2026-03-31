import { readFileSync, readdirSync, statSync, existsSync } from 'fs';
import { resolve, join } from 'path';
import matter from 'gray-matter';
import { classify } from './classifier.js';

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

function countFiles(dir) {
  let count = 0;
  const entries = readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isFile()) {
      count++;
    } else if (entry.isDirectory()) {
      count += countFiles(join(dir, entry.name));
    }
  }
  return count;
}

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

export function parseAllSkills(skillRepoPath) {
  const skills = new Map();

  if (!existsSync(skillRepoPath)) {
    console.error(`skill_repo not found: ${skillRepoPath}`);
    return skills;
  }

  const entries = readdirSync(skillRepoPath, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const skillDir = resolve(skillRepoPath, entry.name);
    const skill = parseSkill(skillDir, entry.name);
    if (skill) {
      skills.set(entry.name, skill);
    }
  }

  return skills;
}
