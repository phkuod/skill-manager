import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { initWatcher } from './watcher.js';
import { createApp } from './app.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(__dirname, '..');
const PORT = process.env.PORT || 3001;
const SKILL_REPO_PATH = process.env.SKILL_REPO_PATH || resolve(rootDir, 'skill_repo');

// Initialize file watcher
initWatcher(SKILL_REPO_PATH);

// Create and start app
const app = createApp(SKILL_REPO_PATH);

app.listen(PORT, () => {
  console.log(`Skill Market API running at http://localhost:${PORT} [${process.env.NODE_ENV || 'development'}]`);
}).on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(`Error: port ${PORT} is already in use. Update the PORT environment variable or ecosystem.config.cjs to use a different port.`);
    process.exit(1);
  }
  throw err;
});

export default app;
