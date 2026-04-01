import { spawn } from 'child_process';
import { createServer } from 'net';
import { rmSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Load env-specific file first (higher priority), then .env as fallback
const nodeEnv = process.env.NODE_ENV || 'development';
dotenv.config({ path: resolve(__dirname, `.env.${nodeEnv}`) });
dotenv.config({ path: resolve(__dirname, '.env') });

const command = process.argv[2];

const PORT = process.env.PORT || 3000;
const API_PORT = process.env.API_PORT || 3001;

function findFreePort(startPort) {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.listen(startPort, () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on('error', (err) => {
      if (err.code === 'EADDRINUSE') {
        resolve(findFreePort(startPort + 1));
      } else {
        reject(err);
      }
    });
  });
}

function run(cmd, args, options = {}) {
  const child = spawn(cmd, args, {
    stdio: 'inherit',
    shell: true,
    cwd: __dirname,
    ...options,
  });
  child.on('error', (err) => {
    console.error(`Failed to start: ${cmd} ${args.join(' ')}`);
    console.error(err.message);
    process.exit(1);
  });
  return child;
}

async function dev() {
  const apiPort = await findFreePort(parseInt(API_PORT));
  if (apiPort !== parseInt(API_PORT)) {
    console.log(`Port ${API_PORT} in use, using ${apiPort} for API`);
  }
  console.log('Starting development servers...');
  const api = run('node', ['server/index.js'], {
    env: { ...process.env, PORT: apiPort, NODE_ENV: 'development' },
  });
  const vite = run('npx', ['vite', '--host'], {
    cwd: resolve(__dirname, 'client'),
    env: { ...process.env, VITE_API_PORT: apiPort },
  });

  process.on('SIGINT', () => {
    api.kill();
    vite.kill();
    process.exit(0);
  });
  process.on('SIGTERM', () => {
    api.kill();
    vite.kill();
    process.exit(0);
  });
}

function build() {
  console.log('Building client...');
  const child = run('npx', ['vite', 'build'], {
    cwd: resolve(__dirname, 'client'),
  });
  child.on('close', (code) => {
    if (code === 0) {
      console.log('Build complete: client/dist/');
    } else {
      console.error(`Build failed with code ${code}`);
      process.exit(code);
    }
  });
}

function start() {
  console.log(`Starting production server on port ${PORT}...`);
  const distPath = resolve(__dirname, 'client', 'dist');
  if (!existsSync(distPath)) {
    console.error('Error: client/dist/ not found. Run "node manage.js build" first.');
    process.exit(1);
  }
  run('node', ['server/index.js'], {
    env: { ...process.env, PORT, NODE_ENV: 'production' },
  });
}

function test() {
  const target = process.argv[3]; // 'server', 'client', or undefined (all)
  const children = [];

  if (!target || target === 'server') {
    console.log('Running server tests...');
    children.push(
      run('npx', ['vitest', 'run', '--config', 'vitest.config.server.js'])
    );
  }

  if (!target || target === 'client') {
    console.log('Running client tests...');
    children.push(
      run('npx', ['vitest', 'run'], { cwd: resolve(__dirname, 'client') })
    );
  }

  let exitCode = 0;
  let completed = 0;
  children.forEach((child) => {
    child.on('close', (code) => {
      if (code !== 0) exitCode = code;
      completed++;
      if (completed === children.length) {
        process.exit(exitCode);
      }
    });
  });
}

function clean() {
  const targets = [
    resolve(__dirname, 'client', 'dist'),
    resolve(__dirname, 'client', 'node_modules', '.vite'),
  ];
  targets.forEach((target) => {
    if (existsSync(target)) {
      rmSync(target, { recursive: true, force: true });
      console.log(`Removed: ${target}`);
    }
  });
  console.log('Clean complete.');
}

const commands = { dev, build, start, test, clean };

if (!command || !commands[command]) {
  console.log(`
Skill Market — manage.js

Usage: node manage.js <command>

Commands:
  dev     Start development servers (Vite + Express)
  build   Build React app to client/dist/
  start   Start production server
  test    Run tests (all, server, or client)
  clean   Remove build artifacts and cache
`);
  process.exit(command ? 1 : 0);
}

commands[command]();
