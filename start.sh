#!/usr/bin/env bash
# start.sh — Start the Skill Market service
# Usage: ./start.sh [dev|development|prod|production|genkey]  (default: development)
#   genkey — print a fresh SECRET_KEY suitable for .env.production and exit
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-development}"

# Normalize short aliases: dev → development, prod → production
case "$MODE" in
  dev)  MODE="development" ;;
  prod) MODE="production"  ;;
esac

# ── genkey: print a fresh SECRET_KEY and exit ─────────────────────────────────
if [ "$MODE" = "genkey" ]; then
  if [ -x "$ROOT/venv/bin/python" ]; then
    PY="$ROOT/venv/bin/python"
  elif [ -x "$ROOT/venv/Scripts/python.exe" ]; then
    PY="$ROOT/venv/Scripts/python.exe"
  else
    PY=python3
  fi
  exec "$PY" -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
fi

# ── Load env file for the selected mode ───────────────────────────────────────
ENV_FILE="$ROOT/.env.$MODE"
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
if [ -x "$ROOT/venv/bin/python" ]; then
  PY="$ROOT/venv/bin/python"
elif [ -x "$ROOT/venv/Scripts/python.exe" ]; then
  PY="$ROOT/venv/Scripts/python.exe"
else
  PY=python3
fi

# ── Collect static files (idempotent) ─────────────────────────────────────────
echo "[start] Collecting static files..."
"$PY" "$ROOT/manage.py" collectstatic --noinput -v 0

# ── Launch ────────────────────────────────────────────────────────────────────
PORT="${PORT:-3000}"

if [ "$MODE" = "production" ]; then
  echo "[start] Starting gunicorn (production) on :$PORT ..."
  export DJANGO_SETTINGS_MODULE=skill_market.settings
  export SKILL_REPO_PATH="${SKILL_REPO_PATH:-$ROOT/skill_repo}"
  export DEBUG="${DEBUG:-False}"
  export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost,127.0.0.1}"
  # NOTE: --workers must stay at 1. Each worker holds its own in-process
  # `_skills` dict and watchdog observer, so >1 workers cause catalog drift
  # across consecutive requests. See CLAUDE.md (Architecture).
  exec gunicorn skill_market.wsgi \
    --bind "0.0.0.0:$PORT" \
    --workers 1 \
    --chdir "$ROOT"
else
  echo "[start] Starting Django dev server on :$PORT ..."
  export SKILL_REPO_PATH="${SKILL_REPO_PATH:-$ROOT/skill_repo}"
  exec "$PY" "$ROOT/manage.py" runserver "0.0.0.0:$PORT"
fi
