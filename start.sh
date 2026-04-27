#!/usr/bin/env bash
# start.sh — Start the Skill Market service
# Usage: ./start.sh [dev|development|prod|production]  (default: development)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$REPO_ROOT/backend"
MODE="${1:-development}"

# Normalize short aliases: dev → development, prod → production
case "$MODE" in
  dev)  MODE="development" ;;
  prod) MODE="production"  ;;
esac

# ── Load env file for the selected mode ───────────────────────────────────────
ENV_FILE="$REPO_ROOT/.env.$MODE"
if [ -f "$ENV_FILE" ]; then
  echo "[start] Loading $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

# ── Pick a Python interpreter ─────────────────────────────────────────────────
# Prefer the project venv; fall back to system python3 (e.g. inside Docker
# where deps are installed system-wide).
if [ -x "$BACKEND/venv/bin/python" ]; then
  PY="$BACKEND/venv/bin/python"
else
  PY=python3
fi

# ── Collect static files (idempotent) ─────────────────────────────────────────
echo "[start] Collecting static files..."
"$PY" "$BACKEND/manage.py" collectstatic --noinput -v 0

# ── Launch ────────────────────────────────────────────────────────────────────
PORT="${PORT:-3000}"

if [ "$MODE" = "production" ]; then
  echo "[start] Starting gunicorn (production) on :$PORT ..."
  export DJANGO_SETTINGS_MODULE=skill_market.settings
  export SKILL_REPO_PATH="${SKILL_REPO_PATH:-$REPO_ROOT/skill_repo}"
  export DEBUG="${DEBUG:-False}"
  export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost,127.0.0.1}"
  exec gunicorn skill_market.wsgi \
    --bind "0.0.0.0:$PORT" \
    --workers 2 \
    --chdir "$BACKEND"
else
  echo "[start] Starting Django dev server on :$PORT ..."
  export SKILL_REPO_PATH="${SKILL_REPO_PATH:-$REPO_ROOT/skill_repo}"
  exec "$PY" "$BACKEND/manage.py" runserver "0.0.0.0:$PORT"
fi
