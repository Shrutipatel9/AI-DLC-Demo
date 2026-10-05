# Infrastructure Specification — U1 Walking Skeleton

**Sources:** `nfr-design/logical-components.md`, `nfr-design/security-design.md`, `nfr-design/reliability-design.md`, team practice `## Deployment` (no hosting in this workflow), and infrastructure answers Q1 (services-only Compose) and Q2 (throwaway CI keys).

This workflow ships no hosted environment. U1's infrastructure is what a developer and the CI runner need: supporting services in Docker Compose, the two apps run as normal processes, and configuration through environment variables. When a host is chosen, the organisation default applies (deploy on merge to staging, with a manual production gate). That is recorded here as the target, not built.

## Deployment

| Facet | Choice | Rationale |
|---|---|---|
| Compute model | Two OS processes: `api` (`uv run uvicorn app.main:app --port 8000 --timeout-graceful-shutdown 10`) and `web` (`pnpm dev` while developing; `pnpm build && pnpm start` for verification and CI). No containers for the apps (answer Q1) | No host is chosen, so Dockerfiles would be guesses. Processes keep the feedback loop fast. The stateless design (scalability design §1) keeps containerising later a packaging step only |
| Supporting services | `docker-compose.yml` at the repository root with `postgres` and `mailpit` | Team practice: Compose for PostgreSQL; Mailpit is the email catcher Playwright reads (NFR8.4) |
| Networking | Everything on `localhost`. Ports: web 3000, api 8000, PostgreSQL 5432, Mailpit SMTP 1025, Mailpit HTTP 8025. The browser calls the API cross-origin (`http://localhost:3000` to `http://localhost:8000`), with CORS allowing only `FRONTEND_ORIGIN` | Matches the production shape (two origins, CORS, Bearer token) so the same code paths are exercised (NFR2.12) |
| TLS | None locally (`APP_ENV=development` or `test`; `Secure` cookies off; no HSTS). The settings validator refuses this combination in any other environment | NFR3.5: TLS is mandatory outside development, enforced at start-up |
| Storage | Named Docker volume `pgdata` for PostgreSQL. No file storage in U1 | Survives restarts; `make db-reset` drops it |
| Environments | `development` (laptop), `test` (pytest and the CI jobs), and `ci-e2e` (production build of the web app against a test API). No staging or production in this workflow | Team Deployment practice |
| Configuration | `backend/.env.example` and `frontend/.env.example` committed with placeholders. Real `.env` files are git-ignored. CI writes its own values into the job environment (see `cicd-pipeline.md`) | NFR6.1, NFR11.4 |
| IaC approach | `docker-compose.yml` plus the GitHub Actions workflow file are the only infrastructure as code. No cloud IaC until a host is chosen | NFR11 hosting neutrality |
| Resource sizing | PostgreSQL 16 with defaults (`max_connections=100`); API pool 5 + 5; AnyIO default 40 threads plus an email limiter of 10; one API process | Sized for the planning assumption of about 2 req/s peak (scalability design §3) |

## Infrastructure Services

| Service | Role | Configuration | Notes |
|---|---|---|---|
| PostgreSQL 16 (`postgres:16` image, pinned by digest in Compose) | Database | Database `app` for development; the test suite creates `app_test`. User and password come from `.env` (`POSTGRES_USER`, `POSTGRES_PASSWORD`). Healthcheck `pg_isready -U $POSTGRES_USER` every 5 s. Port 5432 bound to `127.0.0.1` only | All U1 state, including `rate_limit_hits`. Alembic manages the schema; the API refuses to start if migrations are not at head (reliability design §4) |
| Mailpit (`axllent/mailpit`, pinned by digest) | Email catcher (development and CI only) | SMTP 1025, HTTP API and UI 8025, both bound to `127.0.0.1`. `MP_MAX_MESSAGES=500` | The API sends with `EMAIL_BACKEND=smtp`, `SMTP_HOST=localhost`, `SMTP_PORT=1025`. Playwright reads codes through `GET /api/v1/search?query=to:<email>` |
| Email provider (real) | Email delivery | Not configured in U1. Settings `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` and `SMTP_STARTTLS` are ready for any SMTP provider | Choosing the provider is deferred (`NFR-012`). Changing it is configuration plus, at most, one adapter |
| Load balancer, CDN, DNS, cache, queue | — | None in U1 | Not needed without a host; the design keeps processes stateless for when they are (scalability design §1) |

## Make targets (developer entry points)

| Target | Does |
|---|---|
| `make up` / `make down` | Start or stop the Compose services and wait for their healthchecks |
| `make db-reset` | Drop the `pgdata` volume, start PostgreSQL, run `alembic upgrade head` |
| `make dev` | Run `api` and `web` in development mode (two processes) |
| `make openapi` | Export the OpenAPI document with `app.openapi()` and regenerate the frontend types |
| `make verify` | The skeleton's verification command: run every CI job's commands locally in order (see `cicd-pipeline.md`), including the end-to-end journey against the production web build |

## Shared Infrastructure

U1 is the first unit. It creates the Compose file, the PostgreSQL database, the CI workflow and the platform module that later units extend.

| Shared Resource | Owner Unit | Consumer Units | Access Boundary |
|---|---|---|---|
| PostgreSQL database `app` | U1 (creates it and the Alembic history) | U2–U10 add their own tables through their own migrations | Each component writes only its own tables (domain design ADRs); one Alembic history, migrations named by unit |
| `docker-compose.yml` | U1 | U4 adds file storage settings; U6 adds the worker process | Services are added, never repurposed |
| GitHub Actions workflow | U1 | Every later unit's tests run in the same jobs | New jobs or steps only by pull request; required checks stay required |
| Platform module (settings, logging, limiter, retry, metrics) | U1 | All later units | Imported through `platform` ports only (lint-enforced) |
