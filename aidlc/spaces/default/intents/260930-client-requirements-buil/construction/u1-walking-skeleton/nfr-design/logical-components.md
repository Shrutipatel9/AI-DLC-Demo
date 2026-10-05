# Logical Components — U1 Walking Skeleton

**Sources:** the NFR design files in this folder, `tech-stack-decisions.md` (NFR1.x, NFR7.x, NFR8.x), and `inception/domain-design/components.md` (Identity, WebAuthClient, WebApp).

## 1. Component inventory

| Component | Kind | Owns | NFR patterns applied | Failure domain |
|---|---|---|---|---|
| `web` (Next.js app) | Process | Pages, CSP middleware, `apiClient`, in-memory auth store | Strict CSP, in-memory tokens, request-id surfacing | Browser tab / frontend process |
| `api` (FastAPI app) | Process | Middleware stack, routers, Identity services | Request id, body guard, CORS, headers, auth dependency, error envelope | API process |
| Identity module | Module in `api` | `users`, `one_time_codes`, `verification_attempts`, `refresh_sessions` | Argon2id, HMAC codes, atomic verify, JWT `kid` | Shared with `api` |
| Platform module | Module in `api` | Settings, DB session, logging, metrics, `RateLimiter`, `RetryPolicy`, `EmailSender` ports | Fail-fast settings, pooling, limiter, retry budget | Shared with `api` |
| Email adapter | Adapter | SMTP or fake sending | Retry with budget; commit → send → compensate | One request |
| PostgreSQL | Data store | All U1 state plus `rate_limit_hits` | Row locks, unique indexes, migrations | Whole system (single dependency) |
| Mailpit | Dev and test service | Captured emails | Lets Playwright read codes over its HTTP API (NFR8.4) | Development and CI only |

## 2. Dependency direction (lint-enforced, NFR7.2)

```mermaid
flowchart TD
  R[identity.routes] --> S[identity.services]
  S --> Rep[identity.repositories]
  S --> P[platform ports: RateLimiter, EmailSender, Clock, PasswordHasher, TokenService]
  Rep --> DB[(SQLAlchemy models)]
  A[platform adapters] -.implements.-> P
```
Text fallback: identity routes call identity services. Services call repositories and the platform ports. Repositories use SQLAlchemy models. Platform adapters implement the ports. Import-linter forbids routes from importing repositories or adapters directly, and forbids any module from importing identity internals other than `identity.public`.

Frontend rule: components under `app/` and `components/` may not import `lib/auth/api` or the store's setters; they use the `useAuth()` hook (Section 5.3).

## 3. Shared resources and blast radius

| Shared resource | Shared by | Risk | Isolation |
|---|---|---|---|
| Database pool (5 + 5) | All API requests | Exhaustion stalls the API | No outside calls inside transactions (NFR5.13); 5 s pool timeout; limiter on its own short session |
| Thread pool (40) | Sync endpoints, Argon2, email sends | Slow email sends occupy threads | 25 s send budget; hourly email cap; per-IP limiter |
| `CODE_HMAC_KEY`, `JWT_SIGNING_KEYS` | Identity services | A leak lets codes or tokens be forged | Environment only, `SecretStr`, Gitleaks, rotation via `kid` |
| Email provider | Sign-up and login | Outage blocks new sessions only | Budgeted retries; existing sessions unaffected |

## 4. Local and CI topology (Docker Compose)

| Service | Image or command | Ports | Healthcheck |
|---|---|---|---|
| `postgres` | `postgres:16` | 5432 | `pg_isready` |
| `mailpit` | `axllent/mailpit` | 1025 (SMTP), 8025 (HTTP API) | HTTP 200 on `/livez` |
| `api` | `uv run uvicorn app.main:app` (host process in development; container in the CI e2e job) | 8000 | `GET /health/ready` |
| `web` | `pnpm dev` or `pnpm start` | 3000 | HTTP 200 on `/login` |

Infrastructure Design turns this table into the Compose file and the CI job. No cloud resources are designed in this unit (NFR11).
