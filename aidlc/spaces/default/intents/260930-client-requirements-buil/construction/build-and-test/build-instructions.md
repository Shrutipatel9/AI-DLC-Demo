# Build Instructions

## Prerequisites
- Docker Desktop running; `uv`, `pnpm` (Node 22), `openssl`, `curl`; ports 3000 and 8000 free.
- `docker compose up -d --wait postgres mailpit` starts PostgreSQL and the local mail catcher.
- Face model: `cd backend && uv run python tools/fetch_face_model.py` (pinned MediaPipe Face Landmarker, git-ignored).

## Environment
- Copy `backend/.env.example` → `backend/.env` and `frontend/.env.example` → `frontend/.env.local`; fill placeholders (price/currency, JWT key, OpenAI, Stripe, SMTP). Never commit `.env`.
- Test and verify runs source `scripts/ci-env.sh` (test values, fakes for OpenAI/Stripe, SMTP to Mailpit with credentials blanked).

## Build
- Backend: `cd backend && uv sync --frozen && uv run alembic upgrade head`; API `uv run uvicorn app.main:create_app --factory`; worker `uv run python -m app.worker`.
- Frontend: `cd frontend && pnpm install --frozen-lockfile && pnpm build && pnpm start`.
- Local dev for both: `bash scripts/dev.sh`.

## Verify
- Full gate (same order as CI): `bash scripts/verify.sh`.
- Fast checkpoint journey: `bash scripts/verify-skeleton.sh`.

## Troubleshooting
- Sign-up emails fail in tests → Mailpit port stalled after a Docker restart: `docker compose restart mailpit`.
- "Port 3000/8000 in use" → stop leftover `next start` / `uvicorn` processes.
- Paths on Windows Git Bash: tools receive repo-relative paths; avoid `/d/...` paths for native Python.
