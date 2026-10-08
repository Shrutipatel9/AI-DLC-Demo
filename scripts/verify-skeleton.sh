#!/usr/bin/env bash
# Fast end-to-end proof for each finished Unit (the AI-DLC checkpoint verification command).
#
#   bash scripts/verify-skeleton.sh
#
# Proves the integrated slice works for real: a fresh database with the migration round-trip
# (0001 to 0008), the API (with the pinned face model and the Stripe fake) and the production
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
#   - analysis.spec.ts tagged @checkpoint (U6, extended in U7/U8): paid user -> "Start Analysis" ->
#     the worker process runs the steps (fake AI) -> the progress screen advances -> AI Visuals ->
#     "View my report" -> Home Overview -> the report with its 11 features -> PDF download.
# It must finish in 110 s or less: the script prints the elapsed time and fails above that.
# The full matrix (both viewports, every scenario, axe everywhere) and every other gate stay
# in `bash scripts/verify.sh` and in CI.
#
# Speed (U8): the slow, cacheable steps are skipped only when their inputs are byte-for-byte the
# same as the last successful run, and the web build runs while the database is reset and the API
# starts. Nothing a checkpoint journey checks is dropped or relaxed:
#   - the production web build is reused when the hash of the frontend sources, config and lockfile
#     matches the one recorded after the last good build (`.next/.verify-build-hash`);
#   - `pnpm install` runs only when pnpm-lock.yaml changed (`node_modules/.verify-lock-hash`);
#   - the Playwright browser install runs once per Playwright version (`.verify/playwright-<v>.ok`);
#   - the three migration runs happen in one Python process (tools.migration_roundtrip);
#   - five of the six checkpoint files run side by side on 3 Playwright workers (every journey uses
#     its own freshly signed-up user, so they share no state); the timing-sensitive two-tab
#     journey (1 s budget) runs alone first. `scripts/verify.sh` and CI keep 1 worker.
# Every step prints the seconds elapsed so far, so a slow step is easy to see.
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
WORKER_PID=""
WORKER_LABEL=""
BUILD_PID=""

step() { printf '\n\033[1m==> %s (t=%ss)\033[0m\n' "$*" "$((SECONDS - STARTED_AT))"; }

hash_tree() {
  # A stable hash of the given files and folders (sorted, content only).
  (cd "$ROOT/frontend" && find "$@" -type f 2>/dev/null | LC_ALL=C sort | xargs sha256sum | sha256sum | cut -d' ' -f1)
}

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

stop_worker() {
  # The worker has no port, so it is found by the unique --label this script gave it.
  [ -z "$WORKER_LABEL" ] && return 0
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*app.worker*--label $WORKER_LABEL*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" >/dev/null 2>&1 || true
  fi
  kill -TERM -- "-$WORKER_PID" 2>/dev/null || kill -TERM "$WORKER_PID" 2>/dev/null || true
}

cleanup() {
  [ -n "$BUILD_PID" ] && kill "$BUILD_PID" 2>/dev/null || true
  stop_process "$WEB_PID" 3000
  stop_process "$API_PID" 8000
  stop_worker
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

step "Production web build (in the background; skipped when the sources are unchanged)"
build_web() {
  cd "$ROOT/frontend"
  local lock_hash
  lock_hash="$(sha256sum pnpm-lock.yaml | cut -d' ' -f1)"
  if [ ! -d node_modules ] || [ "$(cat node_modules/.verify-lock-hash 2>/dev/null)" != "$lock_hash" ]; then
    pnpm install --frozen-lockfile --silent
    echo "$lock_hash" >node_modules/.verify-lock-hash
  fi
  local source_hash
  source_hash="$(hash_tree src public next.config.ts tsconfig.json postcss.config.mjs package.json pnpm-lock.yaml)"
  if [ "$(cat .next/.verify-build-hash 2>/dev/null)" = "$source_hash" ] && [ -f .next/BUILD_ID ]; then
    echo "Web build is current (sources unchanged); reusing it."
  else
    rm -f .next/.verify-build-hash
    pnpm build
    echo "$source_hash" >.next/.verify-build-hash
  fi
}
build_web >"$LOG_DIR/build.log" 2>&1 &
BUILD_PID=$!

step "Fresh app_e2e database and migration round-trip"
cd "$ROOT"
docker compose exec -T postgres psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS app_e2e WITH (FORCE)" -c "CREATE DATABASE app_e2e"
cd "$ROOT/backend"
uv sync --frozen --quiet
uv run --no-sync python -m tools.fetch_face_model >/dev/null
uv run --no-sync python -m tools.migration_roundtrip

step "Start the API (SMTP to Mailpit; fresh private media root; E2E landmark overrides)"
rm -rf "$LOG_DIR/media"
API_PID="$(DATABASE_URL="$E2E_DATABASE_URL" EMAIL_BACKEND=smtp MEDIA_ROOT="$LOG_DIR/media" \
  FACE_LANDMARK_OVERRIDES_FILE=tests/fixtures/faces/overrides.json \
  start_background "$LOG_DIR/api.log" uv run --no-sync uvicorn app.main:create_app --factory \
  --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 10)"

step "Wait for the web build and the API"
if ! wait "$BUILD_PID"; then
  BUILD_PID=""
  cat "$LOG_DIR/build.log" >&2
  echo "The production web build failed." >&2
  exit 1
fi
BUILD_PID=""
tail -n 3 "$LOG_DIR/build.log"
cd "$ROOT/frontend"
bash "$ROOT/scripts/wait-for.sh" "http://127.0.0.1:8000/health/ready" 60

step "Start the background worker (U6: fake AI, a short text pause so the steps are visible)"
mkdir -p "$LOG_DIR/ai-control"
rm -f "$LOG_DIR/ai-control/fail-text" "$LOG_DIR/ai-control/fail-image"
export AI_FAKE_CONTROL_DIR="$LOG_DIR/ai-control"
WORKER_LABEL="verify-$$"
WORKER_PID="$(cd "$ROOT/backend" && DATABASE_URL="$E2E_DATABASE_URL" EMAIL_BACKEND=smtp \
  MEDIA_ROOT="$LOG_DIR/media" FACE_LANDMARK_OVERRIDES_FILE=tests/fixtures/faces/overrides.json \
  AI_FAKE_TEXT_DELAY_SECONDS=1 WORKER_POLL_INTERVAL_SECONDS=0.5 \
  start_background "$LOG_DIR/worker.log" uv run --no-sync python -m app.worker --label "$WORKER_LABEL")"
WEB_PID="$(API_ORIGIN="$API_ORIGIN" start_background "$LOG_DIR/web.log" pnpm start --port 3000)"
bash "$ROOT/scripts/wait-for.sh" "http://localhost:3000/login" 60

step "Playwright checkpoint subset (desktop, axe): skeleton + one @checkpoint per unit"
PLAYWRIGHT_VERSION="$(node -p "require('./node_modules/@playwright/test/package.json').version")"
if [ ! -f "$LOG_DIR/playwright-$PLAYWRIGHT_VERSION.ok" ]; then
  pnpm exec playwright install chromium
  : >"$LOG_DIR/playwright-$PLAYWRIGHT_VERSION.ok"
fi
# The two-tab refresh journey asserts a 1 s budget, so it runs alone and first; the other five
# journeys use their own freshly signed-up users and run side by side on 3 workers.
pnpm exec playwright test e2e/session.spec.ts --project=desktop --grep "@checkpoint"
pnpm exec playwright test e2e/skeleton.spec.ts e2e/onboarding.spec.ts e2e/photos.spec.ts   e2e/payments.spec.ts e2e/analysis.spec.ts --project=desktop --grep "@checkpoint" --workers=3

ELAPSED=$((SECONDS - STARTED_AT))
echo "Checkpoint command took ${ELAPSED} s (budget ${BUDGET_SECONDS} s)."
if [ "$ELAPSED" -gt "$BUDGET_SECONDS" ]; then
  echo "The checkpoint command exceeded its ${BUDGET_SECONDS} s budget; investigate before the verifier's hard limit." >&2
  exit 1
fi

step "Skeleton verified end to end."
