# Skill Market

A self-hosted web app for browsing, searching, and installing Claude Code skills from a local skill repository.

![Home](docs/screenshots/01-home.png)
![Skill Detail](docs/screenshots/02-skill-detail.png)

## Features

- Browse skills with real-time search and category filters
- One-click copy of install commands for Claude Code and Opencode
- Download any skill as a ZIP archive
- Dark / light theme (auto-detects system preference)
- Live reload — drop a new skill into `skill_repo/` and the UI updates instantly

## Quick Start

```bash
git clone <repo-url>
cd skill-manager
npm install
node manage.js build
node manage.js start
```

Open [http://localhost:3000](http://localhost:3000).

## Development

```bash
npm install
node manage.js dev
```

Starts the Vite dev server on `http://localhost:3000` (with hot reload) and the Express API on `http://localhost:3001`. Vite proxies `/api` requests to Express automatically.

## Commands

| Command | Description |
|---|---|
| `node manage.js dev` | Start dev servers with hot reload |
| `node manage.js build` | Build React app to `client/dist/` |
| `node manage.js start` | Start production server |
| `node manage.js test` | Run all tests |
| `node manage.js test server` | Server tests only |
| `node manage.js test client` | Client tests only |
| `node manage.js clean` | Remove `dist/` and Vite cache |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `3000` | Production server port |
| `API_PORT` | `3001` | API port in development |
| `SKILL_REPO_PATH` | `./skill_repo` | Path to your skill repository |
| `NODE_ENV` | — | Set to `production` for production builds |

## Production Deployment with PM2

[PM2](https://pm2.keymetrics.io/) keeps the server running and restarts it automatically on failure or reboot.

```bash
npm install -g pm2
node manage.js build
pm2 start ecosystem.config.cjs --env production
pm2 save       # persist the process list
pm2 startup    # enable auto-start on system reboot
```

Common PM2 commands:

```bash
pm2 list                    # view running processes
pm2 logs skill-market       # tail application logs
pm2 restart skill-market    # restart the process
pm2 stop skill-market       # stop the process
pm2 delete skill-market     # remove from PM2
```

## Adding Skills

Drop a folder containing a `SKILL.md` file into `skill_repo/`. The server watches the directory and updates the catalog automatically — no restart needed.

```
skill_repo/
└── my-skill/
    ├── SKILL.md       # required — name, description, license in frontmatter
    └── ...            # any other files
```

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, React Router |
| Backend | Node.js, Express, chokidar, archiver, gray-matter |
| Testing | Vitest, Testing Library |
