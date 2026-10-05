#!/usr/bin/env bash
# Run the API and the web app in development mode (two processes). Ctrl+C stops both.
#
#   bash scripts/dev.sh
#
# Needs backend/.env and frontend/.env.local (copied from the .env.example files) and the
# Compose services (`docker compose up -d --wait postgres mailpit`).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$ROOT/backend/.env" ] || { echo "Missing backend/.env (copy backend/.env.example)." >&2; exit 1; }

(cd "$ROOT/backend" && uv run uvicorn app.main:create_app --factory --reload --port 8000) &
API=$!
(cd "$ROOT/frontend" && pnpm dev --port 3000) &
WEB=$!
trap 'kill "$API" "$WEB" 2>/dev/null || true' EXIT INT TERM
wait
