var fs = require('fs');
var path = require('path');
var matter = require('gray-matter');
var classifier = require('./classifier.js');

var readFileSync = fs.readFileSync;
var readdirSync = fs.readdirSync;
var statSync = fs.statSync;
var existsSync = fs.existsSync;
var resolve = path.resolve;
var join = path.join;
var classify = classifier.classify;

function parseSkillFromDir(dir, skillName) {
  var skillMdPath = join(dir, 'SKILL.md');
  if (!existsSync(skillMdPath)) return null;

  var raw = readFileSync(skillMdPath, 'utf-8');
  var parsed = matter(raw);
  var frontmatter = parsed.data;
  var content = parsed.content;

  var stat = statSync(skillMdPath);
  var fileCount = countFiles(dir);
  var classified = classify(skillName);

  return {
    name: frontmatter.name || skillName,
    description: frontmatter.description || '',
    license: frontmatter.license || 'Unknown',
    category: classified.category,
    icon: classified.icon,
    fileCount: fileCount,
    lastUpdated: stat.mtime.toISOString(),
    content: content,
  };
}

function parseSkill(skillDir, skillName) {
  var versions = detectVersions(skillDir);

  if (versions.length > 0) {
    var currentDir = versions[0].path;
    var skill = parseSkillFromDir(currentDir, skillName);
    if (!skill) return null;

    skill.currentVersion = versions[0].version;
    skill.versions = versions.map(function (v) {
      return { version: v.version, date: v.date };
    }).concat([{ version: 'original', date: null }]);
    return skill;
  }

  var skill = parseSkillFromDir(skillDir, skillName);
  if (!skill) return null;

  skill.currentVersion = null;
  skill.versions = [];
  return skill;
}

function countFiles(dir) {
  var count = 0;
  var entries = readdirSync(dir, { withFileTypes: true });
  for (var i = 0; i < entries.length; i++) {
    var entry = entries[i];
    if (entry.isFile()) {
      count++;
    } else if (entry.isDirectory()) {
      count += countFiles(join(dir, entry.name));
    }
  }
  return count;
}

var VERSION_PATTERN = /^\d{8}-.+/;

function detectVersions(skillDir) {
  if (!existsSync(skillDir)) return [];

  var entries = readdirSync(skillDir, { withFileTypes: true });
  var versions = [];

  for (var i = 0; i < entries.length; i++) {
    var entry = entries[i];
    if (!entry.isDirectory()) continue;
    if (!VERSION_PATTERN.test(entry.name)) continue;

    var versionDir = resolve(skillDir, entry.name);
    var skillMdPath = join(versionDir, 'SKILL.md');
    if (!existsSync(skillMdPath)) continue;

    versions.push({
      version: entry.name,
      path: versionDir,
      date: entry.name.substring(0, 8),
    });
  }

  versions.sort(function (a, b) {
    return b.date.localeCompare(a.date) || b.version.localeCompare(a.version);
  });
  return versions;
}

function parseAllSkills(skillRepoPath) {
  var skills = new Map();

  if (!existsSync(skillRepoPath)) {
    console.error('skill_repo not found: ' + skillRepoPath);
    return skills;
  }

  var entries = readdirSync(skillRepoPath, { withFileTypes: true });
  for (var i = 0; i < entries.length; i++) {
    var entry = entries[i];
    if (!entry.isDirectory()) continue;
    var skillDir = resolve(skillRepoPath, entry.name);
    var skill = parseSkill(skillDir, entry.name);
    if (skill) {
      skills.set(entry.name, skill);
    }
  }

  return skills;
}

module.exports = {
  parseSkillFromDir: parseSkillFromDir,
  parseSkill: parseSkill,
  detectVersions: detectVersions,
  parseAllSkills: parseAllSkills,
};
