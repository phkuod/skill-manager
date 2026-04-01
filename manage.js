var spawn = require('child_process').spawn;
var net = require('net');
var fs = require('fs');
var path = require('path');
var dotenv = require('dotenv');

var resolve = path.resolve;
var existsSync = fs.existsSync;

// Recursive directory removal compatible with Node v10 (no fs.rmSync)
function rmRecursiveSync(targetPath) {
  if (!existsSync(targetPath)) return;
  var stat = fs.lstatSync(targetPath);
  if (stat.isDirectory()) {
    var entries = fs.readdirSync(targetPath);
    for (var i = 0; i < entries.length; i++) {
      rmRecursiveSync(path.join(targetPath, entries[i]));
    }
    fs.rmdirSync(targetPath);
  } else {
    fs.unlinkSync(targetPath);
  }
}

// Load env-specific file first (higher priority), then .env as fallback
var nodeEnv = process.env.NODE_ENV || 'development';
dotenv.config({ path: resolve(__dirname, '.env.' + nodeEnv) });
dotenv.config({ path: resolve(__dirname, '.env') });

var command = process.argv[2];

var PORT = process.env.PORT || 3000;
var API_PORT = process.env.API_PORT || 3001;

function findFreePort(startPort) {
  return new Promise(function (resolve, reject) {
    var server = net.createServer();
    server.listen(startPort, function () {
      var port = server.address().port;
      server.close(function () { resolve(port); });
    });
    server.on('error', function (err) {
      if (err.code === 'EADDRINUSE') {
        resolve(findFreePort(startPort + 1));
      } else {
        reject(err);
      }
    });
  });
}

function run(cmd, args, options) {
  if (!options) options = {};
  var env = options.env || process.env;
  var cwd = options.cwd || __dirname;
  var child = spawn(cmd, args, {
    stdio: 'inherit',
    shell: true,
    cwd: cwd,
    env: env,
  });
  child.on('error', function (err) {
    console.error('Failed to start: ' + cmd + ' ' + args.join(' '));
    console.error(err.message);
    process.exit(1);
  });
  return child;
}

function dev() {
  findFreePort(parseInt(API_PORT)).then(function (apiPort) {
    if (apiPort !== parseInt(API_PORT)) {
      console.log('Port ' + API_PORT + ' in use, using ' + apiPort + ' for API');
    }
    console.log('Starting development servers...');

    var apiEnv = {};
    Object.keys(process.env).forEach(function (k) { apiEnv[k] = process.env[k]; });
    apiEnv.PORT = apiPort;
    apiEnv.NODE_ENV = 'development';

    var viteEnv = {};
    Object.keys(process.env).forEach(function (k) { viteEnv[k] = process.env[k]; });
    viteEnv.VITE_API_PORT = apiPort;

    var api = run('node', ['server/index.js'], { env: apiEnv });
    var vite = run('npx', ['vite', '--host'], {
      cwd: resolve(__dirname, 'client'),
      env: viteEnv,
    });

    process.on('SIGINT', function () {
      api.kill();
      vite.kill();
      process.exit(0);
    });
    process.on('SIGTERM', function () {
      api.kill();
      vite.kill();
      process.exit(0);
    });
  });
}

function build() {
  console.log('Building client...');
  var child = run('npx', ['vite', 'build'], {
    cwd: resolve(__dirname, 'client'),
  });
  child.on('close', function (code) {
    if (code === 0) {
      console.log('Build complete: client/dist/');
    } else {
      console.error('Build failed with code ' + code);
      process.exit(code);
    }
  });
}

function start() {
  console.log('Starting production server on port ' + PORT + '...');
  var distPath = resolve(__dirname, 'client', 'dist');
  if (!existsSync(distPath)) {
    console.error('Error: client/dist/ not found. Run "node manage.js build" first.');
    process.exit(1);
  }
  var env = {};
  Object.keys(process.env).forEach(function (k) { env[k] = process.env[k]; });
  env.PORT = PORT;
  env.NODE_ENV = 'production';
  run('node', ['server/index.js'], { env: env });
}

function test() {
  var target = process.argv[3]; // 'server', 'client', or undefined (all)
  var children = [];

  if (!target || target === 'server') {
    console.log('Running server tests...');
    children.push(
      run('npx', ['vitest', 'run', '--config', 'vitest.config.server.mjs'])
    );
  }

  if (!target || target === 'client') {
    console.log('Running client tests...');
    children.push(
      run('npx', ['vitest', 'run'], { cwd: resolve(__dirname, 'client') })
    );
  }

  var exitCode = 0;
  var completed = 0;
  children.forEach(function (child) {
    child.on('close', function (code) {
      if (code !== 0) exitCode = code;
      completed++;
      if (completed === children.length) {
        process.exit(exitCode);
      }
    });
  });
}

function clean() {
  var targets = [
    resolve(__dirname, 'client', 'dist'),
    resolve(__dirname, 'client', 'node_modules', '.vite'),
  ];
  targets.forEach(function (target) {
    if (existsSync(target)) {
      rmRecursiveSync(target);
      console.log('Removed: ' + target);
    }
  });
  console.log('Clean complete.');
}

var commands = { dev: dev, build: build, start: start, test: test, clean: clean };

if (!command || !commands[command]) {
  console.log('\n' +
    'Skill Market — manage.js\n' +
    '\n' +
    'Usage: node manage.js <command>\n' +
    '\n' +
    'Commands:\n' +
    '  dev     Start development servers (Vite + Express)\n' +
    '  build   Build React app to client/dist/\n' +
    '  start   Start production server\n' +
    '  test    Run tests (all, server, or client)\n' +
    '  clean   Remove build artifacts and cache\n'
  );
  process.exit(command ? 1 : 0);
}

commands[command]();
