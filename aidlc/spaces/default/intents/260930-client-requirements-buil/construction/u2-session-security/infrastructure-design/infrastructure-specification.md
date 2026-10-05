# Infrastructure Specification — U2 Session Security

**Sources:**
- U1 infrastructure specification (still in force)
- U2 NFR design, read with its `post-review-changes.md`
- Team practice `## Deployment`: no hosting in this workflow

U2 adds **no new infrastructure service**. It changes configuration, the database schema and the test journeys only. There were no open infrastructure choices for this unit, so no questions were asked.

## Deployment

| Facet | Choice | Rationale |
|---|---|---|
| Compute model | Unchanged: `api` and `web` as processes; Compose runs `postgres` and `mailpit` | U1 decision (infrastructure Q1) |
| Networking | Unchanged: `localhost:3000` → `localhost:8000`, same site, so the refresh cookie uses `SameSite=Lax` | NFR2.17 cookie site rule |
| Storage | PostgreSQL gains the tables and columns of migration `0002_u2_session_security` | NFR design post-review R-10 |
| Environments | Unchanged (development, test, ci-e2e) | Team Deployment practice |
| IaC approach | Unchanged (Compose and the GitHub Actions workflow) | NFR11 |
| Resource sizing | Unchanged. Refresh adds about 4 requests per hour per active tab | Scalability design |

## Infrastructure Services

| Service | Role | Configuration | Notes |
|---|---|---|---|
| PostgreSQL 16 | Database | Migration `0002`; no server setting changes | Row locks only; no new extensions |
| Mailpit | Email catcher | Unchanged | The reset journey reads password-reset codes from it |
| Background tasks | In-process (FastAPI `BackgroundTasks`) | No infrastructure | Email sent after the response (NFR5.6) |

## New configuration (all in `backend/.env.example` and `scripts/ci-env.sh`)

| Setting | Default | Secret | Notes |
|---|---|---|---|
| `REFRESH_TOKEN_DAYS` | 7 | no | NFR6.1 |
| `RESET_TOKEN_MINUTES` | 10 | no | NFR6.1 |
| `REFRESH_ATTEMPT_RECOVERY_SECONDS` | 60 | no | NFR2.3 |
| `CSRF_ALLOWED_ORIGINS` | value of `FRONTEND_ORIGIN` | no | Also the CORS allow-list (NFR2.17) |
| `REFRESH_RATE_LIMIT_PER_MINUTE` | 60 | no | Requirements post-review R-04 |
| `EMAIL_HASH_KEY` | — (required) | **yes**, ≥ 32 bytes | `ci-env.sh` generates a throwaway value per run with `openssl rand`, as for the other keys |
| `REFRESH_COOKIE_PATH` | `/auth` (validator refuses any other value) | no | NFR2.5 |

## Operational command

| Command | Purpose | How it runs now | Later |
|---|---|---|---|
| `uv run python -m app.identity.cleanup` | Deletes old sessions, used or expired reset tokens and idle shadow counters (NFR11.3) | Manually; documented in `backend/README.md` | A host scheduler runs it daily (NFR design Q1) |

## Shared Infrastructure

| Shared Resource | Owner Unit | Consumer Units | Access Boundary |
|---|---|---|---|
| `refresh_sessions`, `password_reset_tokens`, `email_attempt_counters` | U2 (Identity) | none directly; other units use the Identity public API only | Lint-enforced module boundary |
| Toast service and confirmation dialog | U2 (WebApp) | U3–U10 screens | Imported from `components/feedback` |
