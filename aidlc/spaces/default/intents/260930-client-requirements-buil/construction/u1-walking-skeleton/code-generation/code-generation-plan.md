# Code Generation Plan — U1 Walking Skeleton

## Overview

U1 builds the smallest working end-to-end slice: a visitor signs up, enters the emailed 6-digit code, is signed in and sees "Hi, {name}"; they can log out (reload) and log in again with password + code. It also lays the groundwork every later unit reuses: two apps in one repository, typed configuration, the error format, structured logging, the email port, the per-IP limiter, CI with all quality gates, and the verification command for the skeleton checkpoint.

**Stories:** US1.1, US1.2, US1.3, US1.4, US1.5, US1.6, US1.8, US1.9, US3.1, US3.2, US3.4, US3.8 (46 acceptance criteria).

**Inputs:**
- `functional-design/` (WF-U1-1 to WF-U1-7, BR1.1–BR8.10, entities)
- `nfr-requirements/` (NFR1.1–NFR12.2)
- `nfr-design/` (security, reliability, performance, scalability, observability, logical components)
- `infrastructure-design/` (Compose, CI pipeline, monitoring)
- contract C1 `/auth/register`, `/auth/login`, `/auth/verify`, `/auth/me`, `/health`; C11 error codes.

**Prerequisites on the developer machine:** Python 3.12, `uv`, Node.js 22, `pnpm` (via Corepack), Docker Desktop, Git Bash (for the scripts; `make` is optional because every Make target calls a script in `scripts/`).

**Workspace layout (all at the repository root, never in the record):**

```text
backend/    FastAPI app (app/platform, app/identity, app/health), Alembic, tests
frontend/   Next.js app (src/app, src/lib, src/components), Vitest, Playwright e2e
scripts/    ci-env.sh, verify.sh, check-denylist.sh, export-openapi.sh, wait-for.sh
.github/    workflows/ci.yml, dependabot.yml
docker-compose.yml, Makefile, README.md, .gitignore, .pre-commit-config.yaml, .gitleaks.toml
```

## Decisions carried into the code

These settle details that the design reviews left open, so the code is unambiguous.

| # | Decision | Source |
|---|---|---|
| D1 | Code errors use the contract statuses: `CODE_INVALID` and `CODE_EXPIRED` are **401**, `CODE_LOCKED` and `CODE_RESEND_COOLDOWN` are **429** (the NFR design pseudo-code said 400; the contract wins). | C11, BR2.3, BR2.4 |
| D2 | `X-Requested-With` value is `XMLHttpRequest` (the contract value; the NFR design said `fetch`). | C1 §3 |
| D3 | Contract extension **[Decided by delivery team]**: new error code `RATE_LIMITED` (429, with `Retry-After`) for the per-IP limiter, and an optional integer `attemptsLeft` on error detail items for `CODE_INVALID`. Both are added to the OpenAPI document and the generated types. | NFR2.9, BR2.7, contract C11 gap |
| D4 | An oversized auth body (over 16 KB) returns 422 `VALIDATION_FAILED` with detail reason `BODY_TOO_LARGE`, because C11 has no generic too-large code. | security design §1 |
| D5 | The verify flow follows WF-U1-2 exactly: unknown user, no live code and wrong code give `CODE_INVALID`; only a found-but-expired code gives `CODE_EXPIRED`. The counter row is upserted and then locked, and an expired lock is reset first. | security design §2, NFD review R-01 |
| D6 | Email sends run behind a dedicated `CapacityLimiter(10)`, outside every transaction, with a 25 s deadline enforced by the per-attempt timeout, per-call budget checks and a watchdog. | reliability design §2, NFD review R-02 |
| D7 | The e2e journey and the migration round-trip use a dedicated database `app_e2e`, dropped and recreated on each run, in both CI and `scripts/verify.sh`. The developer's `app` database is never downgraded. | infra review R-02 |
| D8 | `scripts/ci-env.sh` is the single source of the test environment (throwaway keys from `openssl rand`, database URLs, origins, SMTP settings). Both CI and `scripts/verify.sh` source it, and it masks the keys with `::add-mask::` when running in GitHub Actions. | infra review R-01, R-02, R-09 |
| D9 | Branch protection requires the four CI checks but **no approving review**, so a sole maintainer can merge. A review requirement can be switched on when a second maintainer joins. | infra review R-08, team Way of Working |
| D10 | The perf step reports p95 and fails only when a target is exceeded twice in a row (one automatic re-run); it runs on `ubuntu-24.04`. | infra review R-04 |
| D11 | The OpenAPI drift check (`scripts/export-openapi.sh`, then `git diff --exit-code frontend/src/lib/api/types.gen.ts`) runs in the frontend CI job and in `scripts/verify.sh`. | infra review R-11 |
| D12 | The frontend U1 API client attaches the token and handles errors. Proactive refresh and the 401 → refresh → retry single-flight (FE-005, FE-006) arrive with `/auth/refresh` in U2; that is where their test-first cycle happens. In U1, reloading signs the user out (BR5.4). | FD Q3, team Testing Posture |
| D13 | The local branch is renamed `master` → `main` before anything is committed. This plan does not commit or push; commits and the first pull request are made when you ask. | team Way of Working |

## Testing Contract

```json
{
  "version": 1,
  "methodology": "custom",
  "source": "team",
  "ordering": "For the backend JWT and OTP (token and one-time-code) services, the frontend token-refresh and single-flight logic, and the three-photo same-person identity check (`BR-005`), we write failing tests from the acceptance criteria first and then implement; every other layer is implemented first and then its tests are written and run before the Bolt is done.",
  "scope": "classic",
  "test_strategy": "standard",
  "project_type": "greenfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    },
    {
      "layer": "team",
      "text": "Tests are a first-class deliverable in every Bolt. We write tests **after** the code\nin general and **first** for the riskiest logic (interview Q4).\n\n- **Methodology**: custom\n- **Ordering**: For the backend JWT and OTP (token and one-time-code) services, the frontend token-refresh and single-flight logic, and the three-photo same-person identity check (`BR-005`), we write failing tests from the acceptance criteria first and then implement; every other layer is implemented first and then its tests are written and run before the Bolt is done.\n- **Test-first modules (exact list)**: backend JWT service and OTP service\n  (`AUTH-010`–`AUTH-016`); frontend API-client proactive refresh, 401 → refresh →\n  retry, and single-flight logic (`FE-005`, `FE-006`); the identity-check decision\n  logic over the three photos (`BR-005`). Any other module is test-after.\n- **Coverage floor**: each application (backend and frontend) keeps **at least 80%\n  line coverage**, measured over the whole application at every merge and enforced\n  by the tool (`pytest-cov` with `--cov-fail-under=80`; Vitest coverage thresholds\n  `lines: 80`). Coverage exclusions are declared in committed configuration and are\n  never added to make a check pass; the floor may not be weakened (`org.md`).\n- **Requirement coverage**: every `FR-*`, `AUTH-*`, `BR-*` and `FE-*` requirement\n  maps to at least one test (client Section 12 for `FR`/`AUTH`/`BR`; `FE` added by\n  interview Q5). How business-only or blocked IDs are recorded is\n  **[Open — confirm]** (see `evidence.md`).\n- **Backend tooling**: `pytest` + `pytest-cov`; API tests through FastAPI's test\n  client; integration tests against a **real PostgreSQL** database with Alembic\n  migrations applied, never SQLite (`NFR-002`, `NFR-003`).\n- **Frontend tooling**: Vitest + React Testing Library for units and components,\n  including the Zustand auth store and the API client (`FE-001`–`FE-007`).\n- **End-to-end**: a small Playwright set for the main journeys: sign-up/login, and\n  photos → payment → report. It is additive to the Standard test strategy and does\n  not count toward the 80% line floor.\n- **Paid services are faked**: OpenAI, Stripe and the email/OTP provider are\n  replaced by fakes behind their configuration-selected abstractions (`NFR-008`,\n  `NFR-013`). The default test run never calls a paid third-party API.\n- **Test strategy**: the workflow's Standard strategy sets test volume and types;\n  the floors above are additive to it.\n- **CI before merge**: a small **GitHub Actions** workflow is delivered in the first\n  piece of work (the walking skeleton). On every pull request to `main` it runs, for\n  each app: lint (including security rules), format check, type check, tests and\n  the coverage floor. `main` is protected so the workflow must pass before merge\n  (interview Q6). This meets the `org.md` \"CI execution before merge\" floor for\n  `classic`."
    }
  ],
  "obligations": {
    "strategy": "standard",
    "strategy_volume": [
      "Five to eight tests per component.",
      "Unit tests plus integration tests for key boundaries.",
      "Add E2E, performance, or security tests when requirements demand them."
    ],
    "scope_floor": [
      "Keep the existing test suite green.",
      "This scope adds no extra new-test floor beyond the selected test strategy."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "custom",
    "runner_step": "Bootstrap the minimal test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Bootstrap the minimal test runner/configuration and record the exact unit-scoped command.",
      "Custom ordering - For the backend JWT and OTP (token and one-time-code) services, the frontend token-refresh and single-flight logic, and the three-photo same-person identity check (`BR-005`), we write failing tests from the acceptance criteria first and then implement; every other layer is implemented first and then its tests are written and run before the Bolt is done.",
      "Implementation and tests - preserve that exact ordering; do not convert it to layer-local TDD.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:03fb16fc47ef3da40c51217a3dc1655e4655b606e6041af3e826578db6a2b701",
  "contract_sha256": "sha256:c547d86232e1807f6acac4300e6efb06c9bafa5748fa79380bf964ac87c3d5db"
}
```

**How the custom ordering applies in U1:**
- **Test-first (Red, then Green):** the backend **JWT service** (`app/identity/tokens.py`) and the **OTP service** (`app/identity/codes.py`). Each Red run's failing output is recorded in `code-summary.md` before the implementation.
- **Not in U1:** the frontend refresh and single-flight logic (FE-005, FE-006) arrives in U2 with `/auth/refresh` (D12). The BR-005 identity check arrives in U4.
- **Test-after:** every other module is implemented first, and its tests are written and run before the unit is done.

## Steps

### Phase A — Structure and test-runner readiness

- [x] **Step 1 — Repository skeleton** (US1.1, US1.4; AC1.1.1–AC1.1.3, AC1.4.1)
  - Rename the local branch `master` → `main` (D13).
  - Write the root `.gitignore` before any other file (BR8.2).
  - Create the `backend/` and `frontend/` folders, a root `README.md` stub and `.pre-commit-config.yaml` (Gitleaks hook), plus `.gitleaks.toml`.
- [x] **Step 2 — Backend project and production configuration skeleton** (US1.1, US1.5; AC1.5.1–AC1.5.3)
  - `backend/pyproject.toml` (uv; FastAPI, Uvicorn, SQLAlchemy 2, psycopg 3, Alembic, pydantic-settings, argon2-cffi, PyJWT, Jinja2, prometheus-client; dev: pytest, pytest-cov, pytest-socket, httpx, aiosmtpd, mypy, ruff, import-linter) with Ruff (incl. `S`, `D` on services), mypy strict, and import-linter contracts.
  - `app/platform/settings.py`: typed `Settings` with `SecretStr` keys and fail-fast validators (key length, active `kid`, fake email not allowed in production, insecure cookies only in development or test).
  - `app/main.py`: an app factory with a lifespan that validates settings, connects to the database, checks that migrations are at head, and creates the email `CapacityLimiter`.
  - `backend/.env.example` with placeholders only.
- [x] **Step 3 — Frontend project skeleton** (US1.1, US1.9)
  - Next.js (App Router, TypeScript strict) with Tailwind and shadcn/ui (button, input, label, card, form, toast).
  - Zustand, react-hook-form and zod.
  - ESLint (Next + `eslint-plugin-security` + `no-restricted-imports` layering rules) and Prettier.
  - `frontend/.env.example`.
- [x] **Step 4 — Local services** (US1.2; AC1.2.1, AC1.2.3)
  - `docker-compose.yml`: `postgres:16` and `axllent/mailpit`, both pinned by digest and bound to `127.0.0.1`.
  - Compose defaults for credentials, so no `.env` is needed in CI.
  - Healthchecks: `pg_isready`, and `mailpit readyz` (infra review R-05).
  - Named volume `pgdata`.
- [x] **Step 5 — Test runners ready (before the first test-first cycle)**
  - Backend: `pytest.ini` options (markers `perf`, socket blocking with localhost allowed), `tests/conftest.py` (creates and migrates the test database `app_test` against Compose PostgreSQL, a per-test transaction rollback fixture, an injectable `FrozenClock`, and the recording email fake).
  - Frontend: `vitest.config.ts` (jsdom, coverage `lines: 80`, global fetch stub) and `playwright.config.ts` (two projects: 390×844 and 1280×800; `baseURL` from the environment).
  - Run the exact unit-scoped commands from `unit-test-instructions.md`. They must execute and report "no tests" or pass, never error.

### Phase B — Backend platform (test-after)

- [x] **Step 6 — Database, models and migration** (US1.2, US3.1; AC1.2.2, AC1.2.4; NFR1.2)
  - `app/platform/db.py`: engine and pool from settings, `get_session` dependency, rollback on error.
  - `app/identity/models.py`: `users`, `one_time_codes`, `verification_attempts`, `refresh_sessions`.
  - `app/platform/ratelimit_models.py`: `rate_limit_hits`.
  - Alembic environment and `0001_u1_identity` migration with every index from performance design §2.
- [x] **Step 7 — Errors, request id, logging, middleware** (US1.8; AC1.8.2, AC1.8.3; NFR5.6–NFR5.9, NFR5.12)
  - `app/platform/errors.py`: typed `AppError` subclasses mapping to C11 codes, including `RATE_LIMITED` (D3), and exception handlers.
  - `request_id.py`: canonical UUID only.
  - `logging.py`: JSON formatter with the allow-list (`purpose`, `attempt`, `exception` included) and `mask_email`.
  - `middleware.py`, in this order: request id → access log (`unmatched` label) → CORS → security headers → streamed body-size guard (D4).
  - Route classes `PUBLIC_ROUTES`, `DEV_ONLY_ROUTES` and `OPERATIONAL_ROUTES`, with `/docs` and `/openapi.json` only in development.
- [x] **Step 8 — Ports and adapters** (US1.6; AC1.6.1–AC1.6.4; NFR5.1–NFR5.3, NFR5.13, NFR12.x)
  - `clock.py` (`Clock` port).
  - `retry.py` (`RetryPolicy` with jitter and budget).
  - `email/`: `EmailSender` port, SMTP adapter (per-attempt timeout, per-call budget check, watchdog socket shutdown), recording fake (refused in production) and Jinja2 templates `signup_code` and `login_code`.
  - `ratelimit.py`: `RateLimiter` port, in-memory adapter, and PostgreSQL adapter on its own session with `pg_advisory_xact_lock` and a 2 h prune; trusted-proxy client IP.
  - `metrics.py`: opt-in `/metrics` sub-app with a CIDR guard.
- [x] **Step 9 — Platform tests** (test-after; Standard 5–8 per component). Each item lists the tests for one module:
  - settings validators (7);
  - error envelope and handlers (6);
  - request id and access log (5);
  - JSON formatter and log canary — no password, code or token in captured logs (6);
  - security headers and body guard (5);
  - retry policy and budget (6);
  - SMTP adapter against a local stub SMTP server, including a stall after `DATA` returning by 25 s (6);
  - email fake and the production refusal (5);
  - rate limiter on the PostgreSQL adapter, including the 21st request and a rolled-back request still counting (7);
  - metrics guard (5);
  - migration up/down/up (1 integration test).

### Phase C — Identity: test-first services

- [x] **Step 10 — RED: OTP service tests** (US3.1, US3.2, US3.4; AC3.2.1–AC3.2.5, AC3.1.3; BR2.1–BR2.7)
  - Write `tests/identity/test_codes.py` from the acceptance criteria. Cover:
    - 6-digit CSPRNG format;
    - HMAC bound to user and purpose, with constant-time compare;
    - valid at 9:59, expired at 10:00;
    - single use;
    - purpose isolation;
    - 60 s cooldown supersedes the old code;
    - 5th failure locks for 15 minutes;
    - a resend does not reset the count;
    - lock-expiry reset;
    - success resets the count;
    - parallel guesses count exactly 5;
    - two parallel correct submissions give exactly one success.
  - Run them. They must fail, and the failing output is recorded.
- [x] **Step 11 — GREEN: OTP service** — implement `app/identity/codes.py` (issue, verify and the counter logic in the D5 transaction shape) until Step 10 passes. Refactor while green.
- [x] **Step 12 — RED: JWT service tests** (US3.2, US3.8; AC3.2.1, AC3.8.2; BR4.1, BR4.3; AUTH-010–AUTH-012)
  - Write `tests/identity/test_tokens.py`. Cover:
    - claims and the 15-minute expiry (valid at 14:59, invalid at 15:00);
    - HS256 only, with `alg:none` and RS256 headers refused;
    - tampered signature;
    - wrong `typ`;
    - unknown `kid`;
    - rotation, with two keys verifying;
    - start-up refusal for a short key or a missing active `kid`.
  - Run them. They must fail, and the failing output is recorded.
- [x] **Step 13 — GREEN: JWT service** — implement `app/identity/tokens.py` until Step 12 passes. Refactor while green.

### Phase D — Identity: remaining layers (test-after)

- [x] **Step 14 — Passwords and repositories** (US3.1, US3.4; AC3.1.4, AC3.1.5; BR1.2, BR1.5, BR3.1)
  - `passwords.py`: Argon2id hasher with rehash, `PasswordPolicy` with the bundled 10k common-password list, and the dummy hash.
  - `repositories.py`: users, codes, counters and refresh sessions.
  - `cookies.py`: refresh cookie `tokenId.secret` with a stored SHA-256.
- [x] **Step 15 — Identity services and routes** (US3.1, US3.2, US3.4, US3.8; AC3.1.1–AC3.1.5, AC3.2.1–AC3.2.6, AC3.4.1–AC3.4.3, AC3.8.1, AC3.8.2)
  - `services.py`: register, login, verify and me.
    - The flow is commit → send → compensate (D6).
    - Re-sign-up of an unverified email (BR1.4).
    - `EMAIL_ALREADY_REGISTERED`.
    - Masked email.
    - The global email cap.
  - `schemas.py`: camelCase Pydantic models matching C1.
  - `routes.py`: async routes calling `to_thread`.
  - `dependencies.py`: `current_user` and `require_owner` (404).
  - `public.py`.
  - `app/health/routes.py`: async `/health` and `/health/ready`.
- [x] **Step 16 — Identity tests** (test-after):
  - password policy and hasher (7);
  - repositories against real PostgreSQL (5);
  - register API (8): 202 shape, 409, 422 rules, re-sign-up and cooldown 429, no token issued, `BODY_TOO_LARGE`, email failure → 502 with the code superseded;
  - login API (6): generic 401 for unknown, wrong and unverified, the dummy-hash path, 202 with no token, `CODE_LOCKED`;
  - verify API (8): 200 with token and cookie attributes, 401 invalid with `attemptsLeft`, 401 expired, 429 locked, user verified on sign-up, purpose mismatch, unknown email;
  - me and route guard (6): profile shape, 401 variants, the route-enumeration test across all three route classes, `/docs` 404 in production;
  - ownership helper (3);
  - per-IP throttle on the three endpoints (4);
  - email-bulkhead test: `/auth/me` answers during 10 slow sends (1);
  - perf tests, marker `perf` (4): p95 targets NFR9.1–NFR9.3.

### Phase E — Frontend (test-after)

- [x] **Step 17 — API client, config and auth store** (US1.9; AC1.9.1–AC1.9.3; BR5.1–BR5.3)
  - `ApiConfigProvider` (runtime `API_ORIGIN` passed from the root layout).
  - `lib/api/client.ts`: Bearer header, `credentials: "include"`, `X-Requested-With: XMLHttpRequest`, typed `ApiError` carrying `code`, `details` and `requestId`, and a 30 s timeout.
  - `lib/api/types.gen.ts`, generated from the exported OpenAPI document.
  - `lib/auth/store.ts`: Zustand, no `persist`; setters exported only to `lib/auth/*`.
  - `lib/auth/api.ts` and `useAuth()` selectors.
- [x] **Step 18 — CSP middleware and layout** (NFR2.13)
  - `src/middleware.ts`: nonce, CSP on the request and response headers, matcher excluding static assets and prefetches, development variant, runtime `API_ORIGIN`.
  - Root layout reads `headers()` (dynamic rendering).
  - `next.config.ts` headers: nosniff, referrer policy, HSTS outside development.
- [x] **Step 19 — Pages and forms** (US3.1, US3.2, US3.4, US3.8; mockups and interaction spec)
  - `/signup`: name, email, password with live rule hints.
  - `/verify`: masked email; 6-digit input with `inputmode="numeric"`, `autocomplete="one-time-code"` and paste support; expired-code message offering "start again" with the email prefilled (functional design review R-03).
  - `/login`.
  - `/home`: "Hi, {name}" placeholder, protected; an empty store routes to `/login` (BR5.4).
  - Toasts on every outcome, `data-testid` on every interactive element, design tokens from `design-system-mapping.md`, WCAG 2.1 AA.
- [x] **Step 20 — Frontend tests** (test-after):
  - API client (7): headers, `credentials`, error mapping, `requestId`, timeout, no token stored outside memory;
  - auth store (5), including that no Web Storage is touched;
  - signup form (6), verify form (6), login form (5): validation, server error codes to messages, success routing;
  - home page guard (3);
  - CSP middleware (5): nonce present, strict production policy, development variant, matcher, runtime origin;
  - error boundary logs `requestId` (2).

### Phase F — End-to-end, CI and verification

- [x] **Step 21 — Playwright skeleton journey** (US1.2, US3.1, US3.2, US3.4, US3.8; NFR8.4, NFR9.6, NFR9.7)
  - `frontend/e2e/skeleton.spec.ts` covers: sign up → read the code from the Mailpit API → verify → "Hi, {name}" → assert `localStorage` and `sessionStorage` are empty → reload signs out → log in → code → home.
  - axe checks on each screen.
  - Both viewports.
- [x] **Step 22 — Scripts** (D7, D8, D10, D11)
  - `scripts/ci-env.sh`: throwaway keys, masked in GitHub Actions; shared environment.
  - `scripts/wait-for.sh`.
  - `scripts/check-denylist.sh`: an exact package list, including `supabase`, `@supabase/*`, `next-auth`, `@auth/*`, `@clerk/*`, `@auth0/*`, `auth0`, `firebase`, `firebase-admin`, `@okta/*`, `@kinde-oss/*`, `@stytch/*`, `supertokens-*`.
  - `scripts/export-openapi.sh`.
  - `scripts/verify.sh`: runs every CI job's commands in order, against `app_test` and `app_e2e`, and fails fast if ports 3000 or 8000 are busy.
  - `Makefile` targets (`up`, `down`, `db-reset`, `dev`, `openapi`, `verify`) as thin wrappers over the scripts.
- [x] **Step 23 — GitHub Actions and Dependabot** (US1.3, US1.4; AC1.3.1–AC1.3.3, AC1.4.2–AC1.4.4; BR8.6, BR8.9, BR8.10)
  - `.github/workflows/ci.yml` with jobs `backend`, `frontend`, `e2e` and `security`, as in `cicd-pipeline.md`, plus:
    - actions and images pinned by SHA or digest;
    - `persist-credentials: false`;
    - `timeout-minutes` on every job;
    - pinned uv and pnpm versions;
    - `fetch-depth: 0` for Gitleaks;
    - `contents: read` permissions;
    - key environment variables scoped to the steps that need them;
    - the OpenAPI drift step;
    - the perf re-run rule.
  - `.github/dependabot.yml` for uv/pip, npm and github-actions.
  - `docs/branch-protection.md`: the required checks to switch on, with no required review (D9).

### Phase G — Documentation and traceability

- [x] **Step 24 — READMEs and docstrings** (US1.1; AC1.1.2; NFR7.3)
  - `backend/README.md` and `frontend/README.md`: setup, environment keys, commands, layer map.
  - Root `README.md`: prerequisites, `docker compose up`, `scripts/verify.sh`.
  - Docstrings on every service.
- [x] **Step 25 — Full local verification**
  - Run `bash scripts/verify.sh`: lint, types, layering, both coverage floors, perf, the migration round-trip, the e2e journey, Gitleaks, the audits and the deny-list.
  - Fix until green. Never lower a threshold to make a step pass; report any gap instead.
- [x] **Step 26 — Code summary, source manifest and traceability**
  - Write `code-summary.md`, including the Red outputs from Steps 10 and 12.
  - Write `source-manifest.json`, listing every path written.
  - Write `traceability.json`: 46 ACs, NFR1.1–NFR12.2 and BR1.1–BR8.10, each pointing to an implementation or test file.

## Story-to-step traceability

| Story | Steps |
|---|---|
| US1.1 Repository and apps | 1, 2, 3, 24 |
| US1.2 Local environment and migrations | 4, 6, 9, 21, 22 |
| US1.3 CI, test isolation, layering | 2, 3, 5, 23 |
| US1.4 Security tooling | 1, 22, 23 |
| US1.5 Configuration | 2, 9 |
| US1.6 Email adapter | 8, 9 |
| US1.8 Errors, ownership, safe logs | 7, 9, 15, 16 |
| US1.9 Frontend store and API client | 17, 20 |
| US3.1 Sign up | 10, 11, 14, 15, 16, 19, 20, 21 |
| US3.2 Verify code | 10, 11, 12, 13, 15, 16, 19, 20, 21 |
| US3.4 Log in | 10, 11, 14, 15, 16, 19, 20, 21 |
| US3.8 Who am I and protected routes | 12, 13, 15, 16, 19, 21 |

## Quality targets (inputs, never relaxed)
- Line coverage of at least 80% per app (`--cov-fail-under=80`; Vitest `lines: 80`).
- p95 latency: 500 ms for register, login and verify; 100 ms for `/auth/me`; 50 ms for `/health`.
- Auth routes at most 200 KB gzipped.
- No axe WCAG 2.1 AA violations.
- No outside network calls in the default test run.
- Zero Gitleaks findings, and no high or critical advisories.
