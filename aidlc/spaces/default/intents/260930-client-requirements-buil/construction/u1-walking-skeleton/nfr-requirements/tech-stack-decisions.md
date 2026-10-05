# Tech Stack Decisions — U1 Walking Skeleton

These are the foundations every later unit inherits. Client-fixed choices are marked `client`. Choices made in earlier stages cite where they were made. New choices cite this unit's answers (Q1–Q6).

## Backend (`backend/`)

| Area | Choice | Source / rationale |
|---|---|---|
| Language and runtime | Python 3.12 | Q1; current stable, supported by FastAPI, MediaPipe and OpenCV wheels |
| Package and environment manager | `uv` with `pyproject.toml` + `uv.lock` | Q1; fast, reproducible lockfile for `pip-audit` |
| Web framework | FastAPI | client `NFR-001` |
| ASGI server | Uvicorn | Standard FastAPI server |
| Settings | pydantic-settings (typed, from env / `.env`) | BR7.1 |
| ORM | SQLAlchemy 2.0, **synchronous** sessions; FastAPI runs sync endpoints in its thread pool | client `NFR-004`; Q2 |
| Database driver | psycopg 3 | Sync SQLAlchemy 2.0 PostgreSQL driver |
| Migrations | Alembic | client `NFR-003` |
| Database | PostgreSQL 16 (Docker Compose locally) | client `NFR-002`; no hosting assumed |
| Password hashing | `argon2-cffi` (Argon2id) | Q3, NFR2.2 |
| Access tokens | PyJWT, HS256, `kid` header | Q4, NFR2.6 |
| Code hashing | Python `hmac` + SHA-256 | NFR2.5 |
| Rate limiting | Small in-house sliding-window limiter behind an interface (PostgreSQL store) | Q5, NFR2.9, NFR11.2; avoids a new infrastructure dependency |
| Email | `smtplib`-based adapter + recording fake; Mailpit as the local mail catcher | NFR12.1; practices (Docker Compose) |
| Logging | Python `logging` with a JSON formatter and allow-list | NFR5.6 |
| Metrics | `prometheus-client` (disabled by default) | NFR5.10 |
| Tests | pytest, pytest-cov (`--cov-fail-under=80`), httpx TestClient, a PostgreSQL test database, `pytest-socket` to block the network, `freezegun`-style injectable clock | team practices; BR8.7 |
| Lint, format and types | Ruff (lint + format, including `S` security rules), mypy (strict on `app/`) | team practices Q8, Q9 |
| Layering rules | `import-linter` contracts (routers → services → repositories; auth internals private) | BR8.8 |
| Security tooling | Gitleaks (pre-commit + CI), `pip-audit` | team practices Q9 |

## Frontend (`frontend/`)

| Area | Choice | Source / rationale |
|---|---|---|
| Runtime | Node.js 22 LTS | Q1 |
| Package manager | pnpm (`pnpm-lock.yaml`) | Q1 |
| Framework | Next.js (App Router) + TypeScript (`strict`) | client `NFR-005` |
| Auth state | Zustand (no `persist`) | client `FE-001`, `FE-002` |
| UI kit | Tailwind CSS + shadcn/ui | mockups Q2 |
| Forms | react-hook-form + zod | mockups interaction spec |
| API client | One fetch-based client; types generated from the backend OpenAPI document with `openapi-typescript` | contract Q6 |
| Tests | Vitest + React Testing Library (80% line threshold); Playwright for the skeleton journey | team practices Q5 |
| Lint and format | ESLint (Next.js config + `eslint-plugin-security` + `no-restricted-imports` for layering) and Prettier | team practices Q8, BR8.8 |
| Security tooling | `pnpm audit` | team practices Q9 |
| Accessibility check | `@axe-core/playwright` on the auth screens | NFR9; US1.13 begins here |

## Repository and CI

| Area | Choice | Source |
|---|---|---|
| Layout | `backend/`, `frontend/`, `docker-compose.yml`, root `README.md`, `Makefile` | units Q1, practices Q2 |
| Local services | Docker Compose: `postgres:16`, `axllent/mailpit` | practices Q7 |
| CI | GitHub Actions: one workflow with backend and frontend jobs plus an end-to-end job that starts Compose services and runs the Playwright skeleton journey | practices Q6 |
| Branch protection | `main` protected; required checks = all CI jobs | practices Q1 |
| Dependency updates | Dependabot (pip/uv, npm, GitHub Actions) | practices Q9 |
| Verification command (proposed at the checkpoint) | `make verify`: runs backend lint, types and tests, frontend lint, types and tests, the Alembic round-trip and the Playwright skeleton journey against Compose services | delivery Q7 |

## Engineering-quality requirements for this unit

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR1.1 | Two separately runnable apps: `backend/` (FastAPI) and `frontend/` (Next.js), talking over HTTP with CORS. Each builds and starts on its own. | CI builds each app independently. |
| NFR1.2 | Every schema change is an Alembic migration. The U1 migration creates users, one-time codes, attempt counters, refresh sessions and the rate-limit table, and it downgrades cleanly. | CI runs `upgrade head`, `downgrade base`, `upgrade head` on an empty database. |
| NFR1.3 | No Supabase package, SDK or connection string anywhere (`CON-001`). | Lockfile deny-list check (BR8.10). |
| NFR7.1 | Ruff, mypy (strict on `app/`), ESLint, Prettier and `tsc --noEmit` with `strict` all pass. | CI lint and type jobs are required checks. |
| NFR7.2 | Layering is enforced: import-linter contracts in the backend; `no-restricted-imports` stops UI components importing the auth API client (Section 5.3). | The contract checks fail on a seeded violation. |
| NFR7.3 | Each app has a README with setup, environment variables and test commands. Services have docstrings. | Checklist at the checkpoint. |
| NFR8.1 | Backend and frontend each keep line coverage of at least 80%. | `--cov-fail-under=80` and the Vitest threshold in CI. |
| NFR8.2 | The default test run makes no network calls to paid or external services. Email uses the recording fake. | `pytest-socket`; the frontend mocks fetch. |
| NFR8.3 | Test-first for the JWT and code services and for the frontend single-flight refresh client (team Testing Posture). | Bolt commit history shows tests landing before implementation for those modules. |
| NFR8.4 | A Playwright journey covers sign-up, code verification from the mail catcher, the signed-in page, sign-out and login. It reads the code from the Mailpit API, never from a test-only backend endpoint (functional design review R-02). | The E2E job passes in CI and in `make verify`. |
| NFR9.6 | The sign-up, login, code and signed-in screens have no WCAG 2.1 AA violations in axe. | `@axe-core/playwright` assertions in the journey. |
| NFR9.7 | The journey passes at a phone viewport (390×844) and a desktop viewport (1280×800) in Chromium. Other browsers are checked manually at the checkpoint. | Two Playwright projects. |

## Alternatives rejected
- **Async SQLAlchemy:** rejected for Q2 (simplicity; CPU-heavy work later).
- **bcrypt:** rejected for Q3 (Argon2id is the current OWASP first choice).
- **Asymmetric JWT:** rejected for Q4 (one issuer and verifier; HS256 with `kid` rotation is enough and simpler).
- **Redis for rate limiting:** rejected for now (no new infrastructure; the interface allows adding it later).
- **npm:** rejected for Q1 (pnpm is faster with a stricter lockfile).
