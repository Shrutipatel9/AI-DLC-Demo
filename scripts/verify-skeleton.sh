#!/usr/bin/env bash
# Fast end-to-end proof for each finished Unit (the AI-DLC checkpoint verification command).
#
#   bash scripts/verify-skeleton.sh
#
# Proves the integrated slice works for real: a fresh database with the migration round-trip
# (0001 to 0005), the API (with the pinned face model and the Stripe fake) and the production
# web build running together, and the Playwright checkpoint subset at the desktop viewport: the skeleton journey
# plus ONE @checkpoint journey per unit (U4 plan Step 9; every other scenario runs in
# `scripts/verify.sh` and CI):
#   - skeleton.spec.ts: sign up -> emailed code from Mailpit -> home -> reload keeps the
#     session -> log out -> log in again;
#   - session.spec.ts tagged @checkpoint (U2): two tabs refresh together without a logout;
#   - onboarding.spec.ts tagged @checkpoint (U3): consent -> every question with Q19 shown ->
#     disclaimer -> submit;
#   - photos.spec.ts tagged @checkpoint (U4): rules -> three same-person photos through the
#     real MediaPipe model -> review consistent -> Continue;
#   - payments.spec.ts tagged @checkpoint (U5): photo review -> payment screen with the
#     configured price -> Stripe fake hosted checkout -> Pay -> "confirming" -> the signed
#     webhook arrives -> "confirmed" with Start Analysis enabled.
# It must finish in 110 s or less: the script prints the elapsed time and fails above that.
# The full matrix (both viewports, every scenario, axe everywhere) and every other gate stay
# in `bash scripts/verify.sh` and in CI.
#
# Prerequisites: Docker running, uv, pnpm (Node 22), openssl, curl; ports 3000 and 8000 free.
# Uses only the throwaway `app_e2e` database (D7).
set -euo pipefail

STARTED_AT=$SECONDS
BUDGET_SECONDS=110
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/.verify"
if command -v cygpath >/dev/null 2>&1; then LOG_DIR="$(cygpath -m "$LOG_DIR")"; fi
mkdir -p "$LOG_DIR"
export MSYS_NO_PATHCONV=1

API_PID=""
WEB_PID=""

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

port_busy() { curl --silent --max-time 2 "http://127.0.0.1:$1/" >/dev/null 2>&1; }

stop_process() {
  local pid="$1" port="$2"
  [ -z "$pid" ] && return 0
  if command -v taskkill >/dev/null 2>&1; then
    local win_pid
    win_pid="$(netstat -ano 2>/dev/null | grep LISTENING | grep -E "[:.]$port[[:space:]]" | awk '{print $5}' | sort -u | head -1 || true)"
    [ -n "$win_pid" ] && taskkill //PID "$win_pid" //T //F >/dev/null 2>&1 || true
  fi
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
}

cleanup() {
  stop_process "$WEB_PID" 3000
  stop_process "$API_PID" 8000
}
trap cleanup EXIT

start_background() {
  local log="$1"
  shift
  if command -v setsid >/dev/null 2>&1; then
    setsid "$@" >"$log" 2>&1 &
  else
    "$@" >"$log" 2>&1 &
  fi
  echo $!
}

step "Preflight"
for port in 3000 8000; do
  if port_busy "$port"; then
    echo "Port $port is already in use. Stop the process using it and run again." >&2
    exit 1
  fi
done
docker info >/dev/null 2>&1 || { echo "Docker is not running." >&2; exit 1; }
(cd "$ROOT" && docker compose up -d --wait postgres mailpit)
# shellcheck source=/dev/null
source "$ROOT/scripts/ci-env.sh"

step "Fresh app_e2e database and migration round-trip"
cd "$ROOT"
docker compose exec -T postgres psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS app_e2e WITH (FORCE)" -c "CREATE DATABASE app_e2e"
cd "$ROOT/backend"
uv sync --frozen --quiet
uv run python -m tools.fetch_face_model >/dev/null
uv run alembic -x db=e2e upgrade head
uv run alembic -x db=e2e downgrade base
uv run alembic -x db=e2e upgrade head

step "Start the API (SMTP to Mailpit; fresh private media root; E2E landmark overrides)"
rm -rf "$LOG_DIR/media"
API_PID="$(DATABASE_URL="$E2E_DATABASE_URL" EMAIL_BACKEND=smtp MEDIA_ROOT="$LOG_DIR/media" \
  FACE_LANDMARK_OVERRIDES_FILE=tests/fixtures/faces/overrides.json \
  start_background "$LOG_DIR/api.log" uv run uvicorn app.main:create_app --factory \
  --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 10)"

step "Production web build"
cd "$ROOT/frontend"
pnpm install --frozen-lockfile --silent
pnpm build
bash "$ROOT/scripts/wait-for.sh" "http://127.0.0.1:8000/health/ready" 60
WEB_PID="$(API_ORIGIN="$API_ORIGIN" start_background "$LOG_DIR/web.log" pnpm start --port 3000)"
bash "$ROOT/scripts/wait-for.sh" "http://localhost:3000/login" 60

step "Playwright checkpoint subset (desktop, axe): skeleton + one @checkpoint per unit"
pnpm exec playwright install chromium
pnpm exec playwright test e2e/skeleton.spec.ts e2e/session.spec.ts e2e/onboarding.spec.ts \
  e2e/photos.spec.ts e2e/payments.spec.ts --project=desktop --grep "@checkpoint"

ELAPSED=$((SECONDS - STARTED_AT))
echo "Checkpoint command took ${ELAPSED} s (budget ${BUDGET_SECONDS} s)."
if [ "$ELAPSED" -gt "$BUDGET_SECONDS" ]; then
  echo "The checkpoint command exceeded its ${BUDGET_SECONDS} s budget; investigate before the verifier's hard limit." >&2
  exit 1
fi

step "Skeleton verified end to end."
