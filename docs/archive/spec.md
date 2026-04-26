# Skill Market Web UI — Design Spec

## Overview

A self-hosted web application for browsing, searching, and installing skills from a local `skill_repo/` directory. Runs on a private internal network. Users discover skills through a web UI and install them by copying CLI commands into their terminal.

## Goals

- Provide a searchable, browsable interface for the 17 local skills
- Support installing skills to both Claude Code (`~/.claude/skills/`) and Opencode CLI directories
- Offer ZIP download as an alternative install method
- Auto-update skill data when `skill_repo/` changes (watch mode)
- Support dark and light mode

## Non-Goals

- No user authentication (internal network, trusted environment)
- No remote skill sources (local only)
- No direct filesystem writes from the browser (CLI copy commands instead)
- No rating, comments, or social features

## Architecture

**Approach: Monorepo SPA + Express API**

A single Node.js process runs an Express server that:
1. Watches `skill_repo/` for file changes using `chokidar`
2. Parses SKILL.md frontmatter and caches skill data in memory
3. Serves a REST API for skill data and ZIP downloads
4. Serves the built React SPA as static files

```
Browser → Express Server → skill_repo/ (filesystem)
                ↑
          chokidar watcher (auto-refresh on change)
```

## Project Structure

```
skill-manager/
├── manage.js                # CLI entry point: dev, build, clean, start
├── skill_repo/              # Existing skills (data source, untouched)
│   ├── frontend-design/
│   ├── claude-api/
│   └── ...
├── server/                  # Express backend
│   ├── index.js             # Entry point, Express app
│   ├── watcher.js           # chokidar file watcher
│   ├── parser.js            # SKILL.md frontmatter parser
│   ├── classifier.js        # Auto-category mapping
│   └── zipper.js            # ZIP download handler
├── client/                  # React + Vite frontend
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── SkillCard.jsx
│   │   │   ├── SkillDetail.jsx
│   │   │   ├── SearchBar.jsx
│   │   │   ├── CategoryFilter.jsx
│   │   │   ├── InstallCommands.jsx
│   │   │   └── ThemeToggle.jsx
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   └── SkillPage.jsx
│   │   ├── hooks/
│   │   │   └── useSkills.js
│   │   └── context/
│   │       └── ThemeContext.jsx
│   ├── index.html
│   └── vite.config.js
├── package.json             # Dependencies only
└── README.md
```

## manage.js — CLI Entry Point

All project operations go through `node manage.js <command>`:

| Command | Description |
|---------|-------------|
| `node manage.js dev` | Start Vite dev server + Express API concurrently (hot reload) |
| `node manage.js build` | Run `vite build`, output to `client/dist/` |
| `node manage.js start` | Run Express in production (serves API + built static files) |
| `node manage.js clean` | Remove `client/dist/` and `node_modules/.vite` cache |

- `package.json` only declares dependencies — no scripts needed
- `manage.js` uses `child_process` to spawn sub-processes
- Reads `PORT` and `SKILL_REPO_PATH` env vars (defaults: `3000`, `./skill_repo`)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/skills` | List all skills. Supports `?search=` (keyword match on name + description) and `?category=` (filter by category) |
| GET | `/api/skills/:name` | Skill detail: metadata + full SKILL.md content rendered as markdown |
| GET | `/api/skills/:name/zip` | Download the skill folder as a ZIP file |

### Skill Data Shape

```json
{
  "name": "frontend-design",
  "description": "Create distinctive, production-grade frontend interfaces with high design quality.",
  "category": "Development",
  "license": "Complete terms in LICENSE.txt",
  "lastUpdated": "2026-03-26T15:22:00Z",
  "fileCount": 3,
  "icon": "🎨"
}
```

## Auto-Classification

Skills are auto-classified using a static mapping table in `server/classifier.js`. No changes to SKILL.md frontmatter needed.

| Category | Skills |
|----------|--------|
| Development | frontend-design, web-artifacts-builder, mcp-builder, skill-creator |
| Content | doc-coauthoring, internal-comms, brand-guidelines, slack-gif-creator |
| Tools | pdf, docx, pptx, xlsx, canvas-design, theme-factory |
| Data & AI | claude-api, algorithmic-art |
| Testing | webapp-testing |

If a skill is not in the mapping, it defaults to "Other".

## UI Pages

### Home Page

- **Header**: Logo ("SM" badge + "Skill Market") + search bar + dark/light toggle
- **Hero section**: Title "Internal Skill Market" + subtitle with dynamic skill count
- **Category pills**: Horizontal row of clickable filter pills. "All" selected by default. Clicking a category filters the grid.
- **Skill cards grid**: Responsive grid (3 cols desktop, 2 tablet, 1 mobile). Each card shows:
  - Icon (emoji, auto-assigned by category)
  - Skill name
  - Short description (truncated to 2 lines)
  - Category badge (color-coded)
  - Last updated (relative time, e.g., "2d ago")
- **Footer**: Minimal — "Internal Skill Market · {count} skills"

### Skill Detail Page

Accessed by clicking a skill card. URL: `/skill/:name`

- **Back navigation**: "← Back to skills" link
- **Skill header**: Name, full description, category badge, last updated, license
- **Install section**: Tabbed interface with two tabs:
  - **Claude Code tab**: `cp -r {server_path}/skill_repo/{name} ~/.claude/skills/`
  - **Opencode CLI tab**: `cp -r {server_path}/skill_repo/{name} ~/.opencode/skills/`
  - Each tab shows a code block with a "Copy" button
- **Download ZIP button**: Triggers `/api/skills/:name/zip`
- **Skill content**: Full SKILL.md content rendered as formatted markdown

## Theme System

- Two modes: dark and light
- Toggle button in the header (sun/moon icon)
- Implemented via CSS custom properties on `:root`
- Theme preference persisted in `localStorage`
- Default: follows system preference via `prefers-color-scheme` media query

### Color Tokens

| Token | Dark | Light |
|-------|------|-------|
| `--bg-primary` | `#0f172a` | `#ffffff` |
| `--bg-secondary` | `#1e293b` | `#f8fafc` |
| `--bg-card` | `#1e293b` | `#ffffff` |
| `--text-primary` | `#e2e8f0` | `#0f172a` |
| `--text-secondary` | `#94a3b8` | `#64748b` |
| `--border` | `#334155` | `#e2e8f0` |
| `--accent` | `#6366f1` | `#2563eb` |

## File Watcher

- Uses `chokidar` to watch `skill_repo/` recursively
- On any file change (add, modify, delete), re-scans all skill directories
- Rebuilds the in-memory skill cache
- Debounced (300ms) to avoid excessive rebuilds during bulk operations

## Search

- Client sends `?search=` query param to `/api/skills`
- Server performs case-insensitive substring match on `name` and `description`
- Results returned in relevance order (name match > description match)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend framework | React 18 |
| Build tool | Vite |
| Routing | React Router v6 |
| Styling | Tailwind CSS |
| Markdown rendering | react-markdown + remark-gfm |
| Backend | Express |
| File watching | chokidar |
| Frontmatter parsing | gray-matter |
| ZIP generation | archiver |

## Deployment

All operations via `manage.js`:

```bash
node manage.js dev      # Development: Vite hot reload + Express API
node manage.js build    # Build React app to client/dist/
node manage.js start    # Production: Express serves API + static files
node manage.js clean    # Remove build artifacts and cache
```

- The `skill_repo/` path is configurable via `SKILL_REPO_PATH` env var (defaults to `./skill_repo`)
- Port configurable via `PORT` env var (defaults to `3000`)
