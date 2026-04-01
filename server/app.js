var express = require('express');
var path = require('path');
var fs = require('fs');
var classifier = require('./classifier.js');
var zipper = require('./zipper.js');
var fileReader = require('./fileReader.js');
var parser = require('./parser.js');

var resolve = path.resolve;
var existsSync = fs.existsSync;
var getCategories = classifier.getCategories;
var sendZip = zipper.sendZip;
var readSkillFiles = fileReader.readSkillFiles;
var parseSkillFromDir = parser.parseSkillFromDir;

var rootDir = resolve(__dirname, '..');
var NODE_ENV = process.env.NODE_ENV || 'development';
var SKILL_REPO_PATH = process.env.SKILL_REPO_PATH || resolve(rootDir, 'skill_repo');

function createApp(skillRepoPath, options) {
  if (skillRepoPath === undefined) skillRepoPath = SKILL_REPO_PATH;
  if (!options) options = {};

  // Allow injecting getSkills for testability; default to requiring watcher
  var getSkills = options.getSkills || require('./watcher.js').getSkills;

  var app = express();

  function resolveVersionDir(skillName, version) {
    if (version === 'original') {
      return resolve(skillRepoPath, skillName);
    }
    return resolve(skillRepoPath, skillName, version);
  }

  function isValidVersion(skill, version) {
    if (skill.currentVersion === null) return false;
    return skill.versions.some(function (v) { return v.version === version; });
  }

  // Health check
  app.get('/api/health', function (req, res) {
    res.json({ status: 'ok', environment: NODE_ENV, skillCount: getSkills().size });
  });

  // List all skills (with optional search and category filters)
  app.get('/api/skills', function (req, res) {
    var search = req.query.search;
    var category = req.query.category;
    var results = Array.from(getSkills().values()).map(function (skill) {
      var meta = {};
      var keys = Object.keys(skill);
      for (var i = 0; i < keys.length; i++) {
        if (keys[i] !== 'content') {
          meta[keys[i]] = skill[keys[i]];
        }
      }
      return meta;
    });

    if (category && category !== 'All') {
      results = results.filter(function (s) { return s.category === category; });
    }

    if (search) {
      var term = search.toLowerCase();
      results = results.filter(function (s) {
        return s.name.toLowerCase().includes(term) ||
          s.description.toLowerCase().includes(term);
      });
      // Sort: name matches first, then description matches
      results.sort(function (a, b) {
        var aName = a.name.toLowerCase().includes(term) ? 0 : 1;
        var bName = b.name.toLowerCase().includes(term) ? 0 : 1;
        return aName - bName;
      });
    }

    res.json({ skills: results, categories: getCategories() });
  });

  // Skill detail (includes full markdown content)
  app.get('/api/skills/:name', function (req, res) {
    var skill = getSkills().get(req.params.name);
    if (!skill) {
      return res.status(404).json({ error: 'Skill not found: ' + req.params.name });
    }
    var result = {};
    var keys = Object.keys(skill);
    for (var i = 0; i < keys.length; i++) {
      result[keys[i]] = skill[keys[i]];
    }
    result.installPaths = {
      claudeCode: '~/.claude/skills/' + skill.name,
      opencode: '~/.opencode/skills/' + skill.name,
    };
    result.repoPath = resolve(skillRepoPath, req.params.name);
    res.json(result);
  });

  // Download skill as ZIP
  app.get('/api/skills/:name/zip', function (req, res) {
    var skill = getSkills().get(req.params.name);
    if (!skill) {
      return res.status(404).json({ error: 'Skill not found: ' + req.params.name });
    }
    var currentDir = skill.currentVersion
      ? resolve(skillRepoPath, req.params.name, skill.currentVersion)
      : resolve(skillRepoPath, req.params.name);
    sendZip(res, currentDir, req.params.name);
  });

  // List all files in a skill
  app.get('/api/skills/:name/files', function (req, res) {
    var skill = getSkills().get(req.params.name);
    if (!skill) {
      return res.status(404).json({ error: 'Skill not found: ' + req.params.name });
    }
    var currentDir = skill.currentVersion
      ? resolve(skillRepoPath, req.params.name, skill.currentVersion)
      : resolve(skillRepoPath, req.params.name);
    var files = readSkillFiles(currentDir);
    res.json(files);
  });

  // List versions for a skill
  app.get('/api/skills/:name/versions', function (req, res) {
    var skill = getSkills().get(req.params.name);
    if (!skill) {
      return res.status(404).json({ error: 'Skill not found: ' + req.params.name });
    }
    res.json({
      skill: req.params.name,
      currentVersion: skill.currentVersion,
      versions: skill.versions,
    });
  });

  // Get specific version of a skill
  app.get('/api/skills/:name/versions/:version', function (req, res) {
    var skill = getSkills().get(req.params.name);
    if (!skill) {
      return res.status(404).json({ error: 'Skill not found: ' + req.params.name });
    }

    var version = req.params.version;
    if (!isValidVersion(skill, version)) {
      return res.status(404).json({ error: 'Version not found: ' + version });
    }

    var versionDir = resolveVersionDir(req.params.name, version);
    var versionSkill = parseSkillFromDir(versionDir, req.params.name);
    if (!versionSkill) {
      return res.status(404).json({ error: 'Version not found: ' + version });
    }

    var result = {};
    var keys = Object.keys(versionSkill);
    for (var i = 0; i < keys.length; i++) {
      result[keys[i]] = versionSkill[keys[i]];
    }
    result.installPaths = {
      claudeCode: '~/.claude/skills/' + versionSkill.name,
      opencode: '~/.opencode/skills/' + versionSkill.name,
    };
    result.repoPath = versionDir;
    res.json(result);
  });

  // Download specific version as ZIP
  app.get('/api/skills/:name/versions/:version/zip', function (req, res) {
    var skill = getSkills().get(req.params.name);
    if (!skill) {
      return res.status(404).json({ error: 'Skill not found: ' + req.params.name });
    }

    var version = req.params.version;
    if (!isValidVersion(skill, version)) {
      return res.status(404).json({ error: 'Version not found: ' + version });
    }

    var versionDir = resolveVersionDir(req.params.name, version);
    sendZip(res, versionDir, req.params.name + '-' + version);
  });

  // List files in specific version
  app.get('/api/skills/:name/versions/:version/files', function (req, res) {
    var skill = getSkills().get(req.params.name);
    if (!skill) {
      return res.status(404).json({ error: 'Skill not found: ' + req.params.name });
    }

    var version = req.params.version;
    if (!isValidVersion(skill, version)) {
      return res.status(404).json({ error: 'Version not found: ' + version });
    }

    var versionDir = resolveVersionDir(req.params.name, version);
    var files = readSkillFiles(versionDir);
    res.json(files);
  });

  // In production, serve the built React app
  if (NODE_ENV === 'production') {
    var distPath = resolve(rootDir, 'client', 'dist');
    if (existsSync(distPath)) {
      app.use(express.static(distPath));
      app.get('*', function (req, res) {
        if (!req.path.startsWith('/api')) {
          res.sendFile(resolve(distPath, 'index.html'));
        }
      });
    }
  }

  return app;
}

module.exports = { createApp: createApp };
