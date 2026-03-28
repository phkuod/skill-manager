import { spawn } from 'child_process';
import { rmSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const command = process.argv[2];

const PORT = process.env.PORT || 3000;
const API_PORT = process.env.API_PORT || 3001;

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

function dev() {
  console.log('Starting development servers...');
  const api = run('node', ['server/index.js'], {
    env: { ...process.env, PORT: API_PORT, NODE_ENV: 'development' },
  });
  const vite = run('npx', ['vite', '--host'], {
    cwd: resolve(__dirname, 'client'),
    env: { ...process.env, VITE_API_PORT: API_PORT },
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

const commands = { dev, build, start, clean };

if (!command || !commands[command]) {
  console.log(`
Skill Market — manage.js

Usage: node manage.js <command>

Commands:
  dev     Start development servers (Vite + Express)
  build   Build React app to client/dist/
  start   Start production server
  clean   Remove build artifacts and cache
`);
  process.exit(command ? 1 : 0);
}

commands[command]();
