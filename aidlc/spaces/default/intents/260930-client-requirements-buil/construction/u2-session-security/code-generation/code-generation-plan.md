# Code Generation Plan — U2 Session Security

## Overview

U2 completes sign-in and session safety on top of the approved U1 walking skeleton:
- resend and lockout;
- staying signed in across reloads;
- silent refresh, with single flight in a tab and coordination across tabs;
- strict reuse detection, with recovery when a refresh response is lost;
- CSRF and CORS on the cookie endpoints;
- logout, including in every open tab;
- forgot and reset password, and change password;
- the app-wide toast service and confirmation dialog.

**Stories:** US11.7, US3.3, US3.5, US3.6, US3.7, US3.9, US3.10, US3.11, US11.5 (36 acceptance criteria).

**Inputs.** Each design file is read **together with its `post-review-changes.md`**. Those notes amend the files and win on conflict.
- `functional-design/`: WF-U2-1 to WF-U2-9, BR1.1–BR7.5, entities, frontend components.
- `nfr-requirements/`: NFR1.1–NFR11.4, plus NFR2.17 and NFR9.9 from the post-review note.
- `nfr-design/`: security, reliability, performance, scalability and observability designs, and logical components.
- `infrastructure-design/`: settings, CI changes, and the scope of the checkpoint command.
- Contract C1 endpoints: `/auth/resend-code`, `/auth/refresh`, `/auth/logout`, `/auth/password/forgot`, `/auth/password/verify-code`, `/auth/password/reset`, `/auth/change-password`.

**Workspace:** the existing U1 code at the repository root (`backend/`, `frontend/`, `scripts/`, `.github/`). This is brownfield work inside our own skeleton: extend files in place and follow U1's conventions.

## Decisions carried into the code

| # | Decision | Source |
|---|---|---|
| D1 | Every revocation is lock-then-update: `SELECT … FOR UPDATE` on the scope, then a separate `UPDATE`. A refresh re-checks the parent's `revoked_at` after inserting the child. | NFD post-review R-01 |
| D2 | The refresh exchange follows the final pseudocode in the NFD post-review note R-02: lock the parent, then the child; recover by attempt id; error branches return responses rather than raising, so revokes commit; every 401 clears the cookie. | NFD post-review R-02 |
| D3 | Non-revealing endpoints (forgot; resend for the `login` and `password_reset` purposes) do the same work on every branch before the response. Issuing and sending the code happen in a `BackgroundTasks` task that has its own database session. | FD/NFR/NFD post-review R-01/R-03/R-11 |
| D4 | `/auth/login` checks the lockout only **after** a correct password. | NFD post-review R-04, NFR post-review R-01 |
| D5 | Logout revokes the cookie's whole family. On the client, `logout()` takes the `auth-refresh` lock and bumps the generation. | FD post-review R-02, NFD R-08 |
| D6 | Change password verifies the cookie secret, keeps the cookie's family and revokes every other family. Afterwards the client refreshes once; a 401 signs it out with the security message. | NFD post-review R-09, FD R-03 |
| D7 | The refresh cookie uses `Path=/auth` (validator); `REFRESH_COOKIE_SAMESITE` defaults to `lax`, and `none` requires `Secure`. `CORSMiddleware` is the outermost layer, with methods `GET`, `POST`, `OPTIONS` and the extra headers. Origins are normalised. | NFR2.5, NFR2.17, NFD R-06, infra R-03 |
| D8 | The SQLAlchemy engine sets `hide_parameters=True`. This also fixes U1 code-review R-01. | NFR3.2 |
| D9 | The checkpoint command `scripts/verify-skeleton.sh` runs `skeleton.spec.ts` plus `session.spec.ts --grep @checkpoint` at the desktop viewport only, with a 110 s budget guard. CI and `verify.sh` run everything. | Infra post-review R-01 |
| D10 | `scripts/ci-env.sh` raises the test-only rate limits to 1000/min. The limiter tests set the low limits explicitly. | Infra post-review R-02 |
| D11 | Nothing is committed or pushed. | Team practice; your instruction |

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

**How the custom ordering applies in U2.** The Red runs (failing output recorded before implementation) cover:
- the backend **session/JWT refresh logic** (`app/identity/sessions.py`: rotation, reuse detection, attempt-id recovery, revocation; `AUTH-010`–`AUTH-012`);
- the **OTP-based reset-code flow** (`app/identity/password_reset.py`, which reuses the U1 OTP service for `password_reset`; `AUTH-015`);
- the **frontend refresh coordinator** (`lib/auth/refresh-coordinator.ts`: proactive refresh, 401 → refresh → retry, single flight, cross-tab lock and broadcast, generation; `FE-005`, `FE-006`, ADR-006).

Everything else is test-after. The BR-005 identity check is U4.

## Steps

### Phase A — Configuration, schema and runners

- [x] **Step 1 — Settings** (NFR6.1, D7, D8). Changes:
  - New typed settings with validators: `REFRESH_TOKEN_DAYS`, `RESET_TOKEN_MINUTES`, `REFRESH_ATTEMPT_RECOVERY_SECONDS`, `CSRF_ALLOWED_ORIGINS`, `REFRESH_RATE_LIMIT_PER_MINUTE`, `EMAIL_HASH_KEY` (≥ 32 bytes), `REFRESH_COOKIE_SAMESITE`, and `REFRESH_COOKIE_PATH` (must be `/auth`).
  - Engine created with `hide_parameters=True`.
  - `.env.example` placeholders (`EMAIL_HASH_KEY=change-me`).
  - `scripts/ci-env.sh` gets the new values, including the test-only rate limits (D10).
- [x] **Step 2 — Migration `0002_u2_session_security`** (NFR1.1, NFD R-10):
  - creates `password_reset_tokens` and `email_attempt_counters`;
  - adds `flow_started_at`, `revoked_reason` and `attempt_hash`;
  - sets `parent_token_id ON DELETE SET NULL`;
  - adds the indexes from performance design §2;
  - provides a clean downgrade.
  - Models are updated to match.
- [x] **Step 3 — Runners ready.** New empty test modules are collected:
  - backend: `tests/identity/test_sessions.py` and `tests/identity/test_password_reset.py`;
  - frontend: `src/lib/auth/refresh-coordinator.test.ts`.
  - Then run the exact unit-scoped commands from `unit-test-instructions.md`.

### Phase B — Backend: test-first services

- [x] **Step 4 — RED: session service tests** (US3.5, US3.6, US3.7, US3.11; AC3.5.2, AC3.5.3, AC3.6.1, AC3.6.3, AC3.7.2, AC3.7.3; BR2.1–BR2.4, BR3.1). Cover:
  - rotation into the same family; a second exchange of the parent is refused;
  - reuse revokes the family;
  - expiry at 7 days;
  - invalid and revoked cookies;
  - attempt-id recovery (same id within 60 s and child unused → 200); a different id, no id, after 60 s, or child already used → reuse;
  - concurrency: two refreshes → one child; logout vs refresh → zero usable sessions;
  - family logout with a rotated cookie.
  - Run the tests; they must fail, and the output is recorded.
- [x] **Step 5 — GREEN: `app/identity/sessions.py`** (D1, D2, D5) plus repository queries, until Step 4 passes. Refactor while green.
- [x] **Step 6 — RED: password-reset service tests** (US3.9; AC3.9.1–AC3.9.5; BR4.1–BR4.6, FD R-01). Cover:
  - same response for real, unknown, cooldown and locked emails;
  - shadow-counter lockout for unknown emails;
  - code rules;
  - a reset token is issued and earlier ones invalidated;
  - expiry at 10:00;
  - single use, with two concurrent resets → one success;
  - the password rule;
  - all sessions revoked, including when racing a refresh.
  - Run the tests; they must fail, and the output is recorded.
- [x] **Step 7 — GREEN: `app/identity/password_reset.py`** (D3), plus the `EmailAttemptCounter` repository and the background-task sender with its own session, until Step 6 passes. Refactor while green.

### Phase C — Backend: remaining layers (test-after)

- [x] **Step 8 — Resend and lockout** (US3.3; AC3.3.1–AC3.3.4; BR1.1–BR1.6). Changes:
  - `resend_code` in `services.py`;
  - `flow_started_at` windows;
  - signup keeps the visible 429s; login and reset are non-revealing (D3);
  - login step order (D4).
- [x] **Step 9 — Change password** (US11.5; AC11.5.1, AC11.5.3; BR5.1, BR5.3) — `app/identity/password_change.py` (D6).
- [x] **Step 10 — CSRF, CORS and routes** (AC3.6.2; BR2.5; NFR2.7, NFR2.13, NFR2.17):
  - a `require_csrf` dependency;
  - CORS as the outermost layer with origin normalisation (D7);
  - routes for the seven endpoints;
  - the refresh and auth rate limits;
  - cookie set and clear;
  - `/auth/logout` returns 204;
  - security events and metrics (NFR5.9–NFR5.12).
- [x] **Step 11 — Clean-up command** (NFR11.3, NFD R-10) — `python -m app.identity.cleanup`: batched, `SKIP LOCKED`, idempotent.
- [x] **Step 12 — Backend tests** (test-after). Counts per area:
  - resend and lockout API: 7;
  - login lockout order: 3;
  - change-password API: 6, including keeping the family, revoking others, wrong current password → 401 `INVALID_CREDENTIALS`, a missing cookie, and racing a refresh;
  - CSRF header matrix: 6;
  - CORS preflight from allowed and other origins: 4;
  - refresh, logout and reset routes: 6;
  - cookie attributes: 4;
  - log canary for reset token, attempt id, email hash and cookie: 4;
  - metrics series: 2;
  - clean-up, including FK safety and an idempotent second run: 4;
  - settings validators: 5;
  - perf tests: NFR9.1–NFR9.5, plus the anti-enumeration timing test (200 samples per branch).

### Phase D — Frontend: test-first coordinator

- [x] **Step 13 — RED: coordinator tests** (US3.10, US3.11, US3.5; AC3.10.1–AC3.10.5, AC3.11.1, AC3.5.1, AC3.5.2; BR6.1–BR6.6). Uses fake timers and mocked `navigator.locks` and `BroadcastChannel`. Cover:
  - no refresh at 13:59, exactly one by 14:00;
  - three concurrent 401s → one call, each request retried once;
  - a retried 401 is not retried again; a refresh 401 starts no further refresh;
  - a refresh 401 → clear once and navigate once;
  - network error or 5xx → a single retry with the same attempt id, then an error toast and the user stays signed in;
  - a 10 s timeout releases the lock;
  - cross-tab: adopt a broadcast received under 5 s ago; apply a newer broadcast on receipt; logout bumps the generation and a late result is discarded;
  - fallback claim and the no-locks mode.
  - Run the tests; they must fail, and the output is recorded.
- [x] **Step 14 — GREEN: `lib/auth/refresh-coordinator.ts`**, then wire it into `client.ts` (the 401 handler matches only `NOT_AUTHENTICATED`; refresh and logout go through `raw()`) and into `store.ts` (status, `signedOutReason`, generation, `restore()`, `logout()`), until Step 13 passes. Refactor while green.

### Phase E — Frontend: remaining layers (test-after)

- [x] **Step 15 — Feedback components** (US11.7; AC11.7.1–AC11.7.5; BR7.1–BR7.5; NFR9.9). Build:
  - a toast service wrapping Sonner: roles, timing, a close button, phone positioning;
  - `confirm()` with an `AlertDialog` host: Cancel focused first, focus trap, Escape, focus return, a required named confirm label;
  - `FieldError`, adopted by every U1 form.
- [x] **Step 16 — Pages and wiring** (US3.3, US3.5, US3.7, US3.9, US11.5). Build:
  - `AuthBootstrap` with `FullPageLoader`, then `ProtectedRoute`;
  - a `ResendCodeButton` countdown on `/verify`, replacing "start again";
  - `/forgot-password`, `/forgot-password/verify` and `/reset-password` (the reset token kept in memory);
  - `/settings/password`, with a header `UserMenu` link;
  - a header `UserMenu` with Log out (confirm → logout);
  - `SecurityNotice` on `/login`;
  - `data-testid` attributes as listed in `frontend-components.md`.
- [x] **Step 17 — Frontend tests** (test-after). Counts per area:
  - store restore and logout: 6;
  - API client 401 code matching: 5;
  - toast: 6;
  - dialog: 6;
  - resend button: 5;
  - forgot, reset and change forms: 6 each;
  - protected route and loader: 4;
  - security notice: 3;
  - no Web Storage across restore, refresh and two-tab use: 2.

### Phase F — End-to-end, CI, verification, documentation

- [x] **Step 18 — Playwright `e2e/session.spec.ts`** (NFR8.3, NFR9.6, NFR9.7). Scenarios:
  - reload stays signed in, within 1.5 s;
  - two tabs refresh together without being logged out, both valid within 1 s;
  - logout in one tab signs out the other;
  - forgot → code from Mailpit → reset → login with the new password;
  - change password keeps this tab signed in;
  - axe on the dialog, a toast and the new pages.
  - The first four scenarios are tagged `@checkpoint`.
- [x] **Step 19 — Scripts and CI** (D9, D10, infra R-04):
  - `verify-skeleton.sh` runs `skeleton.spec.ts` plus `session.spec.ts --grep @checkpoint` at desktop only, with the 110 s guard;
  - `verify.sh` and `ci.yml` run everything, with the new perf files and both specs.
- [x] **Step 20 — Documentation.** Update the backend README (new settings, the clean-up command, the session model) and the frontend README (the coordinator, feedback components). Add docstrings to the new services.
- [x] **Step 21 — Full verification.** Run `bash scripts/verify.sh` (all gates), then `bash scripts/verify-skeleton.sh` (≤ 110 s). Fix until both are green, and never lower a target.
- [x] **Step 22 — Summary, source manifest and traceability.** Write:
  - `code-summary.md`, including the Red outputs of Steps 4, 6 and 13;
  - `source-manifest.json`, with the exact schema `{stage, unit, version: 1, writes: [{path}]}`;
  - `traceability.json`, covering 36 ACs, BR1.1–BR7.5 and every NFRx.y, each pointing to a file.

## Story-to-step traceability

| Story | Steps |
|---|---|
| US11.7 Feedback everywhere | 15, 16, 17, 18 |
| US3.3 Resend and lockout | 2, 6, 7, 8, 12, 16, 17 |
| US3.5 Stay signed in | 4, 5, 13, 14, 16, 17, 18 |
| US3.6 Reuse detection and CSRF | 4, 5, 10, 12 |
| US3.7 Log out | 4, 5, 13, 14, 15, 16, 18 |
| US3.9 Reset password | 2, 6, 7, 10, 12, 16, 17, 18 |
| US3.10 Quiet renewal | 13, 14, 17 |
| US3.11 Two tabs | 13, 14, 18 |
| US11.5 Change password | 9, 12, 16, 17, 18 |

## Quality targets (inputs, never relaxed)
- **Coverage:** at least 80% of lines per app.
- **Latency (p95):** 200 ms for refresh, logout and resend; 500 ms for forgot, verify-code, reset and change.
- **Restore:** at most 1.5 s. **Two-tab refresh:** at most 1 s.
- **Anti-enumeration:** median and p95 differences under 50 ms.
- **Bundle:** auth routes at most 200 KB gzipped.
- **Accessibility:** zero axe WCAG 2.1 AA violations.
- **Isolation and security:** no outside network calls in tests; zero secrets or high-severity advisories.
- **Checkpoint command:** finishes in 110 s or less.
