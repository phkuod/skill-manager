import chokidar from 'chokidar';
import { parseAllSkills } from './parser.js';

let skills = new Map();
let debounceTimer = null;

export function initWatcher(skillRepoPath) {
  // Initial parse
  skills = parseAllSkills(skillRepoPath);
  console.log(`Loaded ${skills.size} skills from ${skillRepoPath}`);

  // Watch for changes
  const watcher = chokidar.watch(skillRepoPath, {
    ignoreInitial: true,
    persistent: true,
    depth: 5,
  });

  const rebuild = () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      console.log('skill_repo changed, reloading...');
      skills = parseAllSkills(skillRepoPath);
      console.log(`Reloaded ${skills.size} skills`);
    }, 300);
  };

  watcher.on('add', rebuild);
  watcher.on('change', rebuild);
  watcher.on('unlink', rebuild);
  watcher.on('addDir', rebuild);
  watcher.on('unlinkDir', rebuild);

  return watcher;
}

export function getSkills() {
  return skills;
}
