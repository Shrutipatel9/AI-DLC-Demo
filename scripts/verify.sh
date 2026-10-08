#!/usr/bin/env bash
# The walking skeleton's verification command: runs every CI job's checks locally, in the
# same order as .github/workflows/ci.yml (backend, frontend, e2e, security).
#
#   bash scripts/verify.sh
#
# Prerequisites: Docker running, uv, pnpm (Node 22), openssl, curl. Ports 3000 and 8000
# must be free (the script fails fast otherwise). It uses only the throwaway databases
# `app_test` and `app_e2e`; the developer's `app` database is never touched (D7).
# Quality targets are never relaxed here: any failing gate fails the script.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/.verify"
# Native tools (Python, Node) need native paths on Windows Git Bash.
if command -v cygpath >/dev/null 2>&1; then LOG_DIR="$(cygpath -m "$LOG_DIR")"; fi
mkdir -p "$LOG_DIR"
export MSYS_NO_PATHCONV=1 # Git Bash on Windows: do not rewrite container paths
GITLEAKS_IMAGE="ghcr.io/gitleaks/gitleaks:v8.28.0@sha256:cdbb7c955abce02001a9f6c9f602fb195b7fadc1e812065883f695d1eeaba854"

API_PID=""
WEB_PID=""
WORKER_PID=""
WORKER_LABEL=""

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

port_busy() { curl --silent --max-time 2 "http://127.0.0.1:$1/" >/dev/null 2>&1; }

stop_process() {
  local pid="$1" port="$2"
  [ -z "$pid" ] && return 0
  if command -v taskkill >/dev/null 2>&1; then
    # Windows: kill whatever listens on the port, with its process tree.
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
  stop_process "$WEB_PID" 3000
  stop_process "$API_PID" 8000
  stop_worker
}
trap cleanup EXIT

start_background() {
  # $1 = log file, rest = command. Uses setsid when available so the whole tree stops.
  local log="$1"
  shift
  if command -v setsid >/dev/null 2>&1; then
    setsid "$@" >"$log" 2>&1 &
  else
    "$@" >"$log" 2>&1 &
  fi
  echo $!
}

# --------------------------------------------------------------------------- preflight
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

# --------------------------------------------------------------------------- backend
step "Backend: install, lint, format, types, layering"
cd "$ROOT/backend"
uv sync --frozen
uv run python -m tools.fetch_face_model
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict app
uv run lint-imports

step "Backend: tests with coverage (>= 80%), no network"
uv run pytest tests/platform tests/identity tests/health tests/onboarding tests/media \
  tests/face tests/photos tests/payments tests/jobs tests/ai tests/analysis tests/images -m "not perf" \
  --cov=app --cov-report=term-missing --cov-fail-under=80 -q

step "Backend: latency targets (p95; one automatic re-run per target, D10)"
uv run pytest tests/identity/test_perf_auth.py tests/health/test_perf_health.py \
  tests/identity/test_perf_sessions.py tests/identity/test_perf_enumeration.py -m perf -q

# --------------------------------------------------------------------------- frontend
step "Frontend: install, lint, format, types"
cd "$ROOT/frontend"
pnpm install --frozen-lockfile
pnpm lint
pnpm format:check
pnpm typecheck

step "Frontend: tests with coverage (lines >= 80%)"
pnpm exec vitest run --coverage

step "Frontend: production build and bundle budget (<= 200 KB per auth, onboarding, photo, payment, analysis route)"
pnpm build
pnpm size-check

step "OpenAPI drift check (D11)"
bash "$ROOT/scripts/export-openapi.sh" --check

# --------------------------------------------------------------------------- e2e
step "E2E: fresh app_e2e database and migration round-trip (D7)"
cd "$ROOT"
docker compose exec -T postgres psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS app_e2e WITH (FORCE)" -c "CREATE DATABASE app_e2e"
cd "$ROOT/backend"
uv run alembic -x db=e2e upgrade head
uv run alembic -x db=e2e downgrade base
uv run alembic -x db=e2e upgrade head

step "E2E: start the API (SMTP to Mailpit; fresh media root; E2E overrides) and the web build"
rm -rf "$LOG_DIR/media"
API_PID="$(DATABASE_URL="$E2E_DATABASE_URL" EMAIL_BACKEND=smtp MEDIA_ROOT="$LOG_DIR/media" \
  FACE_LANDMARK_OVERRIDES_FILE=tests/fixtures/faces/overrides.json \
  start_background "$LOG_DIR/api.log" uv run uvicorn app.main:create_app --factory \
  --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 10)"
bash "$ROOT/scripts/wait-for.sh" "http://127.0.0.1:8000/health/ready" 60

step "Start the background worker (U6: fake AI, a short text pause so the steps are visible)"
mkdir -p "$LOG_DIR/ai-control"
rm -f "$LOG_DIR/ai-control/fail-text" "$LOG_DIR/ai-control/fail-image"
export AI_FAKE_CONTROL_DIR="$LOG_DIR/ai-control"
WORKER_LABEL="verify-$$"
WORKER_PID="$(cd "$ROOT/backend" && DATABASE_URL="$E2E_DATABASE_URL" EMAIL_BACKEND=smtp \
  MEDIA_ROOT="$LOG_DIR/media" FACE_LANDMARK_OVERRIDES_FILE=tests/fixtures/faces/overrides.json \
  AI_FAKE_TEXT_DELAY_SECONDS=1 WORKER_POLL_INTERVAL_SECONDS=0.5 \
  start_background "$LOG_DIR/worker.log" uv run python -m app.worker --label "$WORKER_LABEL")"
cd "$ROOT/frontend"
WEB_PID="$(API_ORIGIN="$API_ORIGIN" start_background "$LOG_DIR/web.log" pnpm start --port 3000)"
bash "$ROOT/scripts/wait-for.sh" "http://localhost:3000/login" 60

step "E2E: Playwright skeleton, session, onboarding, photo, payment and analysis journeys (phone + desktop, axe)"
pnpm exec playwright install chromium
pnpm exec playwright test e2e/skeleton.spec.ts e2e/session.spec.ts e2e/onboarding.spec.ts \
  e2e/photos.spec.ts e2e/payments.spec.ts e2e/analysis.spec.ts
cleanup
API_PID=""
WEB_PID=""
WORKER_PID=""
WORKER_LABEL=""

# --------------------------------------------------------------------------- security
step "Security: Gitleaks (working tree), dependency audits, auth deny-list, app independence"
cd "$ROOT"
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks dir . --config .gitleaks.toml --redact --no-banner
else
  repo_path="$ROOT"
  command -v cygpath >/dev/null 2>&1 && repo_path="$(cygpath -m "$ROOT")"
  docker run --rm -v "$repo_path:/repo" "$GITLEAKS_IMAGE" \
    dir /repo --config /repo/.gitleaks.toml --redact --no-banner
fi
# pip-audit checks exactly what the committed uv.lock pins.
(cd "$ROOT/backend" \
  && uv export --frozen --no-emit-project --format requirements-txt >"$LOG_DIR/requirements.lock.txt" \
  && uv run pip-audit --strict --progress-spinner off --require-hashes --disable-pip \
    -r "$LOG_DIR/requirements.lock.txt")
(cd "$ROOT/frontend" && pnpm audit --prod --audit-level high)
bash "$ROOT/scripts/check-denylist.sh"
bash "$ROOT/scripts/check-app-independence.sh"

step "All checks passed."
