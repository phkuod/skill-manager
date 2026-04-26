# Skill Market Web UI — Implementation Plan

## Stage 1: Project Scaffolding
**Goal**: Set up the monorepo structure with manage.js, React + Vite frontend, and Express backend
**Success Criteria**:
- `npm install` succeeds
- `node manage.js dev` starts both Vite dev server and Express API
- Express serves a "hello" response at `http://localhost:3000/api/health`
- Vite dev server proxies API requests to Express
- `node manage.js clean` removes build artifacts
**Tasks**:
1. Initialize `package.json` with dependencies only (no scripts)
2. Create `manage.js` — CLI entry point with commands: `dev`, `build`, `start`, `clean`
3. Create `server/index.js` — minimal Express app with `/api/health` endpoint
4. Scaffold `client/` with Vite + React + Tailwind CSS
5. Configure `vite.config.js` with API proxy to Express
6. Install all dependencies: express, chokidar, gray-matter, archiver, react-router-dom, react-markdown, remark-gfm, tailwindcss
**Tests**: Run `node manage.js dev`, verify health endpoint and Vite dev server respond. Run `node manage.js clean`, verify artifacts removed.
**Status**: Not Started

## Stage 2: Backend — Skill Parser, Watcher & API
**Goal**: Express API that reads skill_repo/, watches for changes, and serves skill data
**Success Criteria**:
- `GET /api/skills` returns JSON array of all 17 skills with metadata
- `GET /api/skills/frontend-design` returns full skill detail with SKILL.md content
- `GET /api/skills/pdf/zip` triggers a ZIP download
- Modifying a file in `skill_repo/` auto-updates the API response
**Tasks**:
1. Create `server/parser.js` — reads SKILL.md, extracts frontmatter with gray-matter, collects metadata (name, description, license, file count, last modified)
2. Create `server/classifier.js` — static mapping table that assigns category + icon to each skill
3. Create `server/watcher.js` — chokidar watcher on `skill_repo/`, debounced 300ms, triggers re-parse on change
4. Create `server/zipper.js` — generates ZIP of a skill folder using archiver
5. Wire up Express routes in `server/index.js`:
   - `GET /api/skills` — list all (with `?search=` and `?category=` support)
   - `GET /api/skills/:name` — detail with full markdown content
   - `GET /api/skills/:name/zip` — ZIP download
6. Add error handling (404 for unknown skills, 500 for parse failures)
**Tests**: Use curl or REST client to verify all 3 endpoints. Modify a SKILL.md and verify the API reflects the change.
**Status**: Not Started

## Stage 3: Frontend — Theme System & Layout Shell
**Goal**: React app with dark/light mode, header, and basic routing
**Success Criteria**:
- App renders with header (logo, search bar placeholder, theme toggle)
- Dark/light toggle works, persisted in localStorage
- React Router navigates between Home (`/`) and Skill Detail (`/skill/:name`)
- Tailwind CSS properly configured with custom color tokens
**Tasks**:
1. Set up Tailwind CSS with custom theme tokens (CSS variables for dark/light)
2. Create `ThemeContext.jsx` — React context for theme state, reads `localStorage` and `prefers-color-scheme`
3. Create `ThemeToggle.jsx` — sun/moon icon button
4. Create app layout shell in `App.jsx` — header + main content area + footer
5. Set up React Router with two routes: `/` and `/skill/:name`
6. Create placeholder `Home.jsx` and `SkillPage.jsx` pages
**Tests**: Toggle theme, refresh page (should persist). Navigate between routes.
**Status**: Not Started

## Stage 4: Frontend — Home Page (Search, Filter, Cards)
**Goal**: Fully functional home page with search, category filter, and skill cards
**Success Criteria**:
- Skill cards display all 17 skills in a responsive grid
- Search bar filters skills by name and description in real-time
- Category pills filter skills by category
- Cards show: icon, name, description (truncated), category badge, last updated
- Clicking a card navigates to `/skill/:name`
**Tasks**:
1. Create `useSkills.js` hook — fetches from `/api/skills`, supports search and category params
2. Create `SearchBar.jsx` — input with debounced onChange (300ms)
3. Create `CategoryFilter.jsx` — horizontal pill row, "All" default selected
4. Create `SkillCard.jsx` — card component with icon, name, description, badge, date
5. Wire up `Home.jsx` — compose search + filter + grid, handle state
6. Add responsive grid: 3 cols on desktop (≥1024px), 2 on tablet (≥640px), 1 on mobile
**Tests**: Search for "pdf", verify filtering. Click "Tools" category, verify only Tools skills show. Click a card, verify navigation.
**Status**: Not Started

## Stage 5: Frontend — Skill Detail Page & Install Flow
**Goal**: Skill detail page with rendered markdown, install commands, and ZIP download
**Success Criteria**:
- Page shows skill name, description, category, license, last updated
- Tabbed install section: Claude Code tab and Opencode CLI tab
- Each tab shows a `cp -r` command with a working "Copy" button
- Download ZIP button triggers file download
- Full SKILL.md content rendered as formatted markdown
- Back navigation works
**Tasks**:
1. Create `InstallCommands.jsx` — tabbed component with Claude Code / Opencode tabs, copy-to-clipboard
2. Create `SkillDetail.jsx` — skill header + install section + download button + markdown content
3. Wire up `SkillPage.jsx` — fetch skill detail from `/api/skills/:name`, render SkillDetail
4. Add react-markdown with remark-gfm for rendering SKILL.md content
5. Style the markdown content (code blocks, headings, lists, tables)
6. Add "← Back to skills" link
**Tests**: Navigate to a skill, verify all sections render. Copy command, paste in terminal to verify correctness. Click Download ZIP, verify the file downloads.
**Status**: Not Started

## Stage 6: Production Build & Polish
**Goal**: Production-ready build, single `node manage.js start` command
**Success Criteria**:
- `node manage.js build` runs `vite build`, outputs optimized static files to `client/dist/`
- `node manage.js start` runs Express serving both API and built React app
- `node manage.js clean` removes `client/dist/` and `.vite` cache
- All features work in production mode
- Configurable via env vars: `PORT`, `SKILL_REPO_PATH`
**Tasks**:
1. Configure Express to serve `client/dist/` as static files in production
2. Add SPA fallback (serve `index.html` for all non-API routes)
3. Add `PORT` and `SKILL_REPO_PATH` env var support with defaults
4. Test full production flow: `node manage.js build` then `node manage.js start`, browse → search → install → download
5. Add a minimal README.md with setup and usage instructions
**Tests**: Run `node manage.js build && node manage.js start`, verify all features work at `http://localhost:3000`.
**Status**: Not Started
