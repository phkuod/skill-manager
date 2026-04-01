var fs = require('fs');
var path = require('path');

var readFileSync = fs.readFileSync;
var readdirSync = fs.readdirSync;
var statSync = fs.statSync;
var existsSync = fs.existsSync;
var join = path.join;
var relative = path.relative;
var extname = path.extname;

var MAX_FILE_SIZE = 500 * 1024; // 500 KB

var LANGUAGE_MAP = {
  '.md': 'markdown',
  '.py': 'python',
  '.ts': 'typescript',
  '.tsx': 'typescript',
  '.js': 'javascript',
  '.jsx': 'javascript',
  '.go': 'go',
  '.rb': 'ruby',
  '.java': 'java',
  '.cs': 'csharp',
  '.php': 'php',
  '.sh': 'bash',
  '.json': 'json',
  '.yaml': 'yaml',
  '.yml': 'yaml',
};

function inferLanguage(filePath) {
  var ext = extname(filePath).toLowerCase();
  return LANGUAGE_MAP[ext] || 'text';
}

function isBinary(buffer) {
  var checkLength = Math.min(buffer.length, 8192);
  for (var i = 0; i < checkLength; i++) {
    if (buffer[i] === 0) return true;
  }
  return false;
}

function collectFiles(dir, baseDir, results) {
  var entries = readdirSync(dir, { withFileTypes: true });
  for (var i = 0; i < entries.length; i++) {
    var entry = entries[i];
    var fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      collectFiles(fullPath, baseDir, results);
    } else if (entry.isFile()) {
      var relPath = relative(baseDir, fullPath).replace(/\\/g, '/');
      var stat = statSync(fullPath);
      if (stat.size > MAX_FILE_SIZE) {
        results.push({ path: relPath, content: null, language: inferLanguage(relPath), truncated: true });
        continue;
      }
      var buffer = readFileSync(fullPath);
      if (isBinary(buffer)) continue;
      results.push({
        path: relPath,
        content: buffer.toString('utf-8'),
        language: inferLanguage(relPath),
      });
    }
  }
}

function readSkillFiles(dirPath) {
  if (!existsSync(dirPath)) return [];

  var results = [];
  collectFiles(dirPath, dirPath, results);

  results.sort(function (a, b) {
    if (a.path === 'SKILL.md') return -1;
    if (b.path === 'SKILL.md') return 1;
    return a.path.localeCompare(b.path);
  });

  return results;
}

module.exports = { inferLanguage: inferLanguage, readSkillFiles: readSkillFiles };
