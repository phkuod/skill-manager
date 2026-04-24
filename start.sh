#!/usr/bin/env bash
# start.sh — Start the Skill Market service
# Usage: ./start.sh [dev|prod]  (default: dev)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$REPO_ROOT/backend"
VENV="$BACKEND/venv"
MODE="${1:-dev}"

# ── Checks ────────────────────────────────────────────────────────────────────
# ── Select requirements file based on Python version ──────────────────────────
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "unknown")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo "0")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")

if [ "$PY_MAJOR" = "3" ] && [ "$PY_MINOR" -ge 12 ]; then
  REQUIREMENTS="$BACKEND/requirements_py3.12.txt"
elif [ "$PY_MAJOR" = "3" ] && [ "$PY_MINOR" -ge 10 ]; then
  REQUIREMENTS="$BACKEND/requirements_py3.10_plus.txt"
else
  REQUIREMENTS="$BACKEND/requirements_py3.8_3.9.txt"
fi

if [ ! -d "$VENV" ]; then
  echo "ERROR: virtualenv not found at $VENV"
  echo "       Run:  python3 -m venv $VENV && $VENV/bin/pip install -r $REQUIREMENTS"
  exit 1
fi

source "$VENV/bin/activate"

# ── Collect static files (idempotent) ─────────────────────────────────────────
echo "[start] Collecting static files..."
python "$BACKEND/manage.py" collectstatic --noinput -v 0

# ── Launch ────────────────────────────────────────────────────────────────────
if [ "$MODE" = "prod" ]; then
  echo "[start] Starting gunicorn (production) on :3000 ..."
  export DJANGO_SETTINGS_MODULE=skill_market.settings
  export SKILL_REPO_PATH="${SKILL_REPO_PATH:-$REPO_ROOT/skill_repo}"
  export DEBUG=False
  export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost,127.0.0.1}"
  exec gunicorn skill_market.wsgi \
    --bind 0.0.0.0:3000 \
    --workers 2 \
    --chdir "$BACKEND"
else
  echo "[start] Starting Django dev server on :3000 ..."
  export SKILL_REPO_PATH="${SKILL_REPO_PATH:-$REPO_ROOT/skill_repo}"
  exec python "$BACKEND/manage.py" runserver 0.0.0.0:3000
fi
