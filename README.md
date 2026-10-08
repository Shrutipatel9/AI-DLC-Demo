# AI Facial Analysis Platform

Two independent applications in one repository. They share no source code and talk to
each other **only over HTTP** (CORS, Bearer access token, httpOnly refresh cookie).

| App | Stack | Docs |
|---|---|---|
| `backend/` | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 | [backend/README.md](backend/README.md) |
| `frontend/` | Next.js 16 (App Router), TypeScript strict, Zustand, Tailwind | [frontend/README.md](frontend/README.md) |

Authentication is custom and backend-controlled: sign-up and login each finish with a
6-digit code sent by email. There is no third-party auth service.

## Prerequisites

- Python 3.12 via [uv](https://docs.astral.sh/uv/)
- Node.js 22 and pnpm 10 (`corepack enable`)
- Docker Desktop (PostgreSQL and the Mailpit email catcher run in Compose)
- Git Bash on Windows (the scripts are Bash). `make` is optional: every target calls a script.

## Run it locally

```bash
docker compose up -d --wait postgres mailpit   # PostgreSQL :5432, Mailpit :1025 / UI :8025
cp backend/.env.example backend/.env           # then fill in the placeholders
cp frontend/.env.example frontend/.env.local
(cd backend && uv sync && uv run python -m tools.fetch_face_model && uv run alembic upgrade head)
(cd frontend && pnpm install)
bash scripts/dev.sh                            # API on :8000, web on :3000 (or see below)
```

Open http://localhost:3000, sign up, and read your code in Mailpit at http://localhost:8025.

On Windows, use `127.0.0.1` (not `localhost`) for PostgreSQL and SMTP in `backend/.env`:
Docker Desktop's IPv6 `localhost` forwarding can stall connections for about 30 seconds.

## Verify everything (the walking-skeleton check)

```bash
bash scripts/verify.sh      # or: make verify
```

It runs every CI job locally, in order:

- **backend**: Ruff (lint, including the `S` security rules, and format), `mypy --strict`, import-linter layering, pytest with at least 80% coverage, and the p95 latency checks;
- **frontend**: ESLint (security and layering rules), Prettier, `tsc`, Vitest with at least 80% line coverage, the production build, the 200 KB bundle budget, and the OpenAPI drift check;
- **e2e**: a fresh `app_e2e` database, the Alembic round-trip, then the Playwright journeys (skeleton, session, onboarding, photos, payments) on phone and desktop viewports with axe accessibility checks;
- **security**: Gitleaks, `pip-audit`, `pnpm audit`, and the auth-as-a-service deny-list.

Ports 3000 and 8000 must be free. The script uses only the throwaway databases `app_test`
and `app_e2e`; your `app` database is never touched.

## Scripts

| Script | Does |
|---|---|
| `scripts/verify.sh` | All CI checks locally (above) |
| `scripts/ci-env.sh` | `source` it: the test environment, with throwaway keys from `openssl rand` |
| `scripts/dev.sh` | API and web in development mode |
| `scripts/export-openapi.sh [--check]` | Regenerate `frontend/src/lib/api/types.gen.ts` (or fail on drift) |
| `scripts/check-denylist.sh` | Fail if Supabase or an auth-as-a-service SDK appears in a lockfile |
| `scripts/wait-for.sh URL [s]` | Wait for a URL to answer |

## Repository rules

- Trunk is `main`. Work arrives through short-lived branches and pull requests, squash-merged; CI must pass (see [docs/branch-protection.md](docs/branch-protection.md)).
- Never commit secrets or `.env` files. Only `.env.example` files with placeholders are committed. Gitleaks runs as a pre-commit hook (`pre-commit install`) and in CI.
- Schema changes ship only as Alembic migrations.
- Pull-request descriptions cite the requirement IDs they implement (`FR-*`, `AUTH-*`, `BR-*`, `FE-*`).
