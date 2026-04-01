var chokidar = require('chokidar');
var parser = require('./parser.js');
var parseAllSkills = parser.parseAllSkills;

var skills = new Map();
var debounceTimer = null;

function initWatcher(skillRepoPath) {
  // Initial parse
  skills = parseAllSkills(skillRepoPath);
  console.log('Loaded ' + skills.size + ' skills from ' + skillRepoPath);

  // Watch for changes
  var watcher = chokidar.watch(skillRepoPath, {
    ignoreInitial: true,
    persistent: true,
    depth: 5,
  });

  var rebuild = function () {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
      console.log('skill_repo changed, reloading...');
      skills = parseAllSkills(skillRepoPath);
      console.log('Reloaded ' + skills.size + ' skills');
    }, 300);
  };

  watcher.on('add', rebuild);
  watcher.on('change', rebuild);
  watcher.on('unlink', rebuild);
  watcher.on('addDir', rebuild);
  watcher.on('unlinkDir', rebuild);

  return watcher;
}

function getSkills() {
  return skills;
}

module.exports = { initWatcher: initWatcher, getSkills: getSkills };
