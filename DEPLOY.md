# Deployment

Django serves both the HTML pages and the `/api/*` JSON surface from a single gunicorn process managed by PM2.

Docker (`docker build -t skill-market . && docker run -p 9419:9419 skill-market`) is for **simulating prod locally only**. The real production deployment uses the gunicorn/PM2 path below.

---

## Pre-deploy checklist (applies to both modes)

Do every item before exposing the service.

- [ ] **`SECRET_KEY`** — generated fresh, not the example string.
      `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- [ ] **`DEBUG=False`** in `backend/.env.production`.
- [ ] **`ALLOWED_HOSTS`** — includes the public hostname/IP the API will be reached at (comma-separated).
- [ ] **`CORS_ALLOWED_ORIGINS`** — for split deploy, set to the **single** frontend origin (e.g. `https://skills.intra.example`). Browsers reject comma lists. For an internal-only tool you can keep `*`.
- [ ] **`PORT`** — bind port for gunicorn (default `9419`).
- [ ] **`SKILL_REPO_PATH`** — absolute path to the curated `skill_repo/` on the host.
- [ ] **`backend/.env`** — does NOT exist on the prod host, OR matches the prod values. This file is gitignored, loaded by `settings.py` *before* `os.environ.get(...)`, and silently overrides everything. A leftover dev `backend/.env` will hijack `CORS_ALLOWED_ORIGINS`/`DEBUG`/`SECRET_KEY` even when `backend/.env.production` looks correct.
- [ ] **`INSTALL_TARGET_<NAME>_*`** — every target you want users to install to has all required keys (`_TYPE`, `_BASE`; plus `_HOST`/`_USER`/`_SSH_KEY` for `ssh` type). `_BASE` includes `{user_name}` unless you intentionally want users to overwrite each other.
- [ ] **SSH targets only** — `rsync` and `openssh-client` are installed on the backend host; the SSH key file referenced by `_SSH_KEY` is `chmod 600` and the remote `authorized_keys` accepts it non-interactively (no passphrase prompt).
- [ ] **Tests pass on the deploy commit.** From `backend/` with venv active: `pytest`. (E2E `pytest e2e/` requires a Chromium; skip on minimal hosts.)
- [ ] **`git status` clean** — no uncommitted changes accidentally going to prod.

---

## Deploy (PM2 + gunicorn)

Django serves both the HTML pages and the API from one origin.

```bash
# 1. Get the code on the host
git clone <repo-url> /srv/skill-market
cd /srv/skill-market

# 2. Set up the venv (Linux paths)
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt   # prod-only

# 3. Configure env
cp backend/.env.production.example backend/.env.production
$EDITOR backend/.env.production    # apply the checklist values

# 4. Make sure no stale dev override exists
[ -f backend/.env ] && echo "REMOVE backend/.env BEFORE PROCEEDING" && exit 1

# 5. Smoke-launch directly first (so failures aren't hidden behind PM2)
./backend/start.sh prod
# Ctrl-C once you've seen "Listening at: http://0.0.0.0:9419"

# 6. Hand off to PM2
pm2 start backend/ecosystem.config.cjs
pm2 save
pm2 startup        # follow the printed command to register the boot hook
```

Then run the [post-deploy smoke tests](#post-deploy-smoke-tests) against `http://<host>:9419/`.

**Rolling updates (after the first deploy):**

```bash
cd /srv/skill-market
git pull
backend/venv/bin/pip install -r backend/requirements.txt   # only if requirements.txt changed
pm2 restart skill-market
pm2 logs skill-market --lines 50
```

`backend/start.sh` re-runs `collectstatic` on every launch, so static asset changes pick up automatically.

---

## Post-deploy smoke tests

Run these against the deployed origin(s) before announcing the rollout. They map 1-to-1 to the failure modes seen in field testing.

- [ ] `curl -fsS https://<backend>/api/skills | head -c 200` — returns JSON, status 200, count matches expectation.
- [ ] `curl -fsS -H 'Origin: https://<frontend>' -D - -o /dev/null https://<backend>/api/skills | grep -i access-control-allow-origin` — header echoes the frontend origin (or matches the configured single origin).
- [ ] `curl -fsS -X OPTIONS -H 'Origin: https://<frontend>' -H 'Access-Control-Request-Method: POST' -D - -o /dev/null https://<backend>/api/install/run` — returns 204 with `Access-Control-Allow-Methods: GET, POST, OPTIONS`.
- [ ] **Browse to the frontend in a real browser.** The home page lists all skills (count matches the `skill_repo/` on the backend host).
- [ ] Type a query in the search bar — results re-rank.
- [ ] Click a skill card → detail page renders with paste-and-run command, sidebar populated, documentation rendered.
- [ ] Click **Install** on a skill → modal opens. Either:
      a) Lists configured targets (shows the install button enabled when a target is picked), OR
      b) Shows "No install targets configured…" if you intentionally left `INSTALL_TARGET_*` unset.
- [ ] **Toggle the theme** (gear/moon icon, top-right). Both light and dark themes render every screen without contrast failures or missing borders. (Memory rule: visual UI checks must cover both themes.)
- [ ] **Run the install modal UI audit** if the modal markup changed since the last release: open `/skills/<some-skill>/`, paste `backend/skills/static/skills/dev/install-modal-ui-audit.js` into DevTools console, run. Expect `{passed: 64+, failed: 0}`.
- [ ] **Issue one real install** (any target) end-to-end and confirm the file landed where `_BASE` says it should.
- [ ] **Tail the logs for 60 seconds**: `pm2 logs skill-market`. No stack traces, no `[ERROR]`.

---

## Common issues

| Symptom | Most likely cause | Fix |
|---|---|---|
| Browser shows "blocked by CORS policy" even though `backend/.env.production` has the right origin | Stale `backend/.env` on the host overriding `CORS_ALLOWED_ORIGINS` | `cat backend/.env` — delete or sync it |
| Install modal opens but lists no targets | `INSTALL_TARGET_*` env vars not in scope of the gunicorn process | `pm2 show skill-market`, confirm env; `pm2 restart skill-market --update-env` after editing `backend/.env.production` |
| Install button enabled but POST returns 401-ish "no session" | The `CURRENT_USER_NAME` cookie isn't set on the browser for the backend origin | Set it via your auth proxy / SSO. For split deploys the cookie must be on the *backend* origin and `SameSite=None; Secure` so the browser sends it cross-origin |
| Detail page shows "no files" or empty content | `SKILL_REPO_PATH` points at a path that doesn't exist on the host | Check the env value; `ls $SKILL_REPO_PATH/<skill>/SKILL.md` |
| Catalog count differs between gunicorn workers | Each worker keeps its own in-process `_skills` dict and its own watchdog observer (known limitation with `--workers 2`) | Either (a) reduce to `--workers 1`, (b) accept the few-second drift after a `skill_repo/` change, or (c) `pm2 restart skill-market` to force a sync |
| Some Tailwind utility class renders nothing | `backend/skills/static/skills/vendor/tailwind.min.css` is JIT-purged and the class wasn't in the build | Use an inline `style=""` or a class already in the bundle. Audit script catches this for the install modal |
| `backend/start.sh` fails with `bash: ./backend/start.sh: cannot execute: required file not found` | CRLF line endings (repo cloned on Windows) | `sed -i 's/\r$//' backend/start.sh && chmod +x backend/start.sh` (the Dockerfile does this automatically) |

---

## Rollback

```bash
cd /srv/skill-market
git log --oneline -5                  # find the last-known-good SHA
git checkout <good-sha>
pm2 restart skill-market
```

There is no database to migrate, so a checkout-and-restart is a complete rollback.
