var path = require('path');
var dotenv = require('dotenv');
var watcher = require('./watcher.js');
var appModule = require('./app.js');

var resolve = path.resolve;
var initWatcher = watcher.initWatcher;
var createApp = appModule.createApp;

var rootDir = resolve(__dirname, '..');

// Load env-specific file first (higher priority), then .env as fallback
var nodeEnv = process.env.NODE_ENV || 'development';
dotenv.config({ path: resolve(rootDir, '.env.' + nodeEnv) });
dotenv.config({ path: resolve(rootDir, '.env') });

var PORT = process.env.PORT || 3001;
var SKILL_REPO_PATH = process.env.SKILL_REPO_PATH || resolve(rootDir, 'skill_repo');

// Initialize file watcher
initWatcher(SKILL_REPO_PATH);

// Create and start app
var app = createApp(SKILL_REPO_PATH);

app.listen(PORT, function () {
  console.log('Skill Market API running at http://localhost:' + PORT + ' [' + (process.env.NODE_ENV || 'development') + ']');
}).on('error', function (err) {
  if (err.code === 'EADDRINUSE') {
    console.error('Error: port ' + PORT + ' is already in use. Update the PORT environment variable or ecosystem.config.cjs to use a different port.');
    process.exit(1);
  }
  throw err;
});

module.exports = app;
