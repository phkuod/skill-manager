import { readFileSync, readdirSync, statSync, existsSync } from 'fs';
import { join, relative, extname } from 'path';

const MAX_FILE_SIZE = 500 * 1024; // 500 KB

const LANGUAGE_MAP = {
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

export function inferLanguage(filePath) {
  const ext = extname(filePath).toLowerCase();
  return LANGUAGE_MAP[ext] || 'text';
}

function isBinary(buffer) {
  const checkLength = Math.min(buffer.length, 8192);
  for (let i = 0; i < checkLength; i++) {
    if (buffer[i] === 0) return true;
  }
  return false;
}

function collectFiles(dir, baseDir, results) {
  const entries = readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      collectFiles(fullPath, baseDir, results);
    } else if (entry.isFile()) {
      const relPath = relative(baseDir, fullPath).replace(/\\/g, '/');
      const stat = statSync(fullPath);
      if (stat.size > MAX_FILE_SIZE) {
        results.push({ path: relPath, content: null, language: inferLanguage(relPath), truncated: true });
        continue;
      }
      const buffer = readFileSync(fullPath);
      if (isBinary(buffer)) continue;
      results.push({
        path: relPath,
        content: buffer.toString('utf-8'),
        language: inferLanguage(relPath),
      });
    }
  }
}

export function readSkillFiles(dirPath) {
  if (!existsSync(dirPath)) return [];

  const results = [];
  collectFiles(dirPath, dirPath, results);

  results.sort((a, b) => {
    if (a.path === 'SKILL.md') return -1;
    if (b.path === 'SKILL.md') return 1;
    return a.path.localeCompare(b.path);
  });

  return results;
}
