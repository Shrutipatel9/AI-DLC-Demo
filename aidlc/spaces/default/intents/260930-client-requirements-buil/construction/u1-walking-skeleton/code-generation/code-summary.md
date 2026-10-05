# Code Summary — U1 Walking Skeleton

**Unit:** `u1-walking-skeleton` · **Stories:** US1.1, US1.2, US1.3, US1.4, US1.5, US1.6, US1.8, US1.9, US3.1, US3.2, US3.4, US3.8 (46 acceptance criteria).

**Testing contract:** `custom` (team). The backend OTP service and JWT service were written test-first: failing tests were run and recorded before any implementation. Every other layer is test-after.

All application code is at the workspace root (`backend/`, `frontend/`, `scripts/`, `.github/`, `docs/`, `docker-compose.yml`, `Makefile`, `README.md`, `.gitignore`, `.pre-commit-config.yaml`, `.gitleaks.toml`). Every path is listed in `source-manifest.json`. Nothing is committed yet (D13). The local branch was renamed `master` → `main`.

## What was built

| Area | Where | Notes |
|---|---|---|
| Backend app factory and route classes | `backend/app/main.py`, `app/platform/routing.py` | `create_app()` (run with `uvicorn app.main:create_app --factory`). The lifespan checks the database and that migrations are at head. The public router must equal `PUBLIC_ROUTES`. `/docs` exists only in development; `/metrics` is opt-in with a CIDR guard |
| Settings | `app/platform/settings.py` | Typed. Fails fast on: short keys, unknown `kid`, the fake email adapter outside development/test, insecure cookies outside development/test, SMTP without TLS in production, an SMTP username without a password. Error messages name the setting, never the value |
| Errors, request id, logging, middleware | `app/platform/errors.py`, `request_id.py`, `logging.py`, `middleware.py` | C11 envelope, including `RATE_LIMITED` and `attemptsLeft` (D3). Middleware order: request id → access log → CORS → security headers → 16 KB body guard (422 `BODY_TOO_LARGE`, D4) → catch-all 500. JSON logs keep only allow-listed fields; emails are masked |
| Database and migration | `app/platform/db.py`, `app/identity/models.py`, `app/platform/ratelimit_models.py`, `alembic/versions/0001_u1_identity.py` | All performance-design indexes. Unique `lower(email)`. Unique live code per (user, purpose) |
| Ports and adapters | `app/platform/clock.py`, `retry.py`, `ratelimit.py`, `metrics.py`, `email/` | SMTP adapter with a per-attempt timeout, a per-command budget check and a watchdog. Recording fake that production refuses. Dispatcher with an email bulkhead (`CapacityLimiter(10)`) and a 25 s budget (D6). PostgreSQL limiter on its own session, with an advisory lock |
| OTP service (test-first) | `app/identity/codes.py` | 6-digit CSPRNG codes. HMAC over `user:purpose:code`. Valid before 10:00. Single use. 60 s cooldown that supersedes the old code. Fifth failure locks for 15 minutes. Verify transaction follows D5 |
| JWT service (test-first) | `app/identity/tokens.py` | HS256 only. `kid` rotation. Required claims. `typ=access`. Expiry checked against the injected clock |
| Identity services and routes | `app/identity/services.py`, `routes.py`, `dependencies.py`, `schemas.py`, `passwords.py`, `cookies.py`, `repositories.py`, `public.py` | Commit → send → compensate. Argon2id with re-hash. 10k common-password list (SecLists, MIT). Dummy hash for unknown accounts. httpOnly refresh cookie storing an id plus a SHA-256 hash. `require_owner` returns 404 |
| Health | `app/health/routes.py` | `async` `/health` and `/health/ready` (2 s limit, 503 with no details) |
| OpenAPI export | `backend/tools/export_openapi.py`, `scripts/export-openapi.sh` | Generates `frontend/src/lib/api/types.gen.ts`, with a drift check (D11) |
| Frontend API client and auth store | `frontend/src/lib/api/`, `src/lib/auth/`, `src/lib/config/api-config.tsx` | Single client: Bearer token, `credentials: "include"`, `X-Requested-With: XMLHttpRequest` (D2), 30 s timeout, typed `ApiError`. Zustand store in memory only. UI sees selectors and actions only |
| CSP | `frontend/src/proxy.ts`, `src/lib/config/csp.ts`, `next.config.ts`, `src/app/layout.tsx` | Nonce plus `strict-dynamic`. The API origin is read at request time. Development variant. Static security headers |
| Pages | `src/app/{signup,verify,login,home}`, `src/components/{auth,app,ui}` | Live password rules. One-field numeric code input. Expired code offers "start again" with the email prefilled. Toasts on every outcome. `data-testid` on every interactive element. Design tokens in `src/styles/tokens.css` |
| E2E | `frontend/e2e/skeleton.spec.ts`, `playwright.config.ts` | Sign up → code from Mailpit → home → Web Storage empty → reload signs out → log in → code → home. axe on four screens. Phone and desktop viewports |
| Local services | `docker-compose.yml` | `postgres:16` and `axllent/mailpit`, pinned by digest, bound to 127.0.0.1, with healthchecks |
| CI and supply chain | `.github/workflows/ci.yml`, `.github/dependabot.yml`, `docs/branch-protection.md`, `.pre-commit-config.yaml`, `.gitleaks.toml` | Jobs `backend`, `frontend`, `e2e`, `security`. Actions pinned by SHA. Read-only token. `persist-credentials: false`. Timeouts on every job |
| Scripts | `scripts/ci-env.sh`, `verify.sh`, `wait-for.sh`, `check-denylist.sh`, `check-app-independence.sh`, `export-openapi.sh`, `dev.sh`; `Makefile` | `verify.sh` is the skeleton verification command |

## Red evidence (test-first modules)

Each Red run executed against an interface-only skeleton module. It had signatures and types, and its bodies raised `NotImplementedError`, so every test was collected (no import or collection errors) and failed on behaviour. The implementations were written afterwards: Step 11 for codes, Step 13 for tokens.

### OTP service — `uv run pytest tests/identity/test_codes.py -q` (Step 10)

```text
=========================== short test summary info ===========================
FAILED tests/identity/test_codes.py::test_generated_codes_are_six_digits_from_secrets
FAILED tests/identity/test_codes.py::test_real_codes_are_digits_only
FAILED tests/identity/test_codes.py::test_hash_is_bound_to_user_and_purpose
FAILED tests/identity/test_codes.py::test_only_the_hash_is_stored
FAILED tests/identity/test_codes.py::test_comparison_is_constant_time
FAILED tests/identity/test_codes.py::test_code_is_valid_at_nine_fifty_nine
FAILED tests/identity/test_codes.py::test_code_is_expired_at_ten_minutes_and_not_counted
FAILED tests/identity/test_codes.py::test_a_code_can_be_used_once
FAILED tests/identity/test_codes.py::test_signup_code_is_refused_for_login
FAILED tests/identity/test_codes.py::test_resend_cooldown_then_new_code_supersedes_old
FAILED tests/identity/test_codes.py::test_cooldown_is_per_purpose
FAILED tests/identity/test_codes.py::test_supersede_makes_a_code_unverifiable
FAILED tests/identity/test_codes.py::test_fifth_failure_locks_for_fifteen_minutes
FAILED tests/identity/test_codes.py::test_lock_ends_at_fifteen_minutes_and_resets_the_count
FAILED tests/identity/test_codes.py::test_resend_does_not_reset_the_failure_count
FAILED tests/identity/test_codes.py::test_success_resets_the_failure_count
FAILED tests/identity/test_codes.py::test_no_live_code_counts_as_a_failure
FAILED tests/identity/test_codes.py::test_unknown_user_gets_plain_invalid_and_nothing_is_counted
FAILED tests/identity/test_codes.py::test_policy_values_are_configurable
FAILED tests/identity/test_codes.py::test_parallel_wrong_guesses_count_exactly_five
FAILED tests/identity/test_codes.py::test_two_parallel_correct_submissions_give_one_success
FAILED tests/identity/test_codes.py::test_issue_time_is_utc_aware
22 failed in 0.98s
```

Green (Step 11): `22 passed`.

### JWT service — `uv run pytest tests/identity/test_tokens.py -q` (Step 12)

```text
=========================== short test summary info ===========================
FAILED tests/identity/test_tokens.py::test_access_token_claims_and_header
FAILED tests/identity/test_tokens.py::test_each_token_has_a_unique_id
FAILED tests/identity/test_tokens.py::test_valid_at_fourteen_fifty_nine_invalid_at_fifteen
FAILED tests/identity/test_tokens.py::test_alg_none_is_refused
FAILED tests/identity/test_tokens.py::test_other_algorithms_are_refused
FAILED tests/identity/test_tokens.py::test_tampered_signature_and_payload_are_refused
FAILED tests/identity/test_tokens.py::test_token_signed_with_another_key_is_refused
FAILED tests/identity/test_tokens.py::test_wrong_token_type_is_refused[reset]
FAILED tests/identity/test_tokens.py::test_wrong_token_type_is_refused[refresh]
FAILED tests/identity/test_tokens.py::test_wrong_token_type_is_refused[None]
FAILED tests/identity/test_tokens.py::test_unknown_or_missing_kid_is_refused
FAILED tests/identity/test_tokens.py::test_garbage_is_refused[]
FAILED tests/identity/test_tokens.py::test_garbage_is_refused[not-a-token]
FAILED tests/identity/test_tokens.py::test_garbage_is_refused[a.b]
FAILED tests/identity/test_tokens.py::test_garbage_is_refused[a.b.c.d]
FAILED tests/identity/test_tokens.py::test_garbage_is_refused[....]
FAILED tests/identity/test_tokens.py::test_missing_required_claims_are_refused
FAILED tests/identity/test_tokens.py::test_rotation_accepts_both_keys_during_overlap
FAILED tests/identity/test_tokens.py::test_start_up_refuses_short_key_or_missing_active_kid
FAILED tests/identity/test_tokens.py::test_built_from_settings
20 failed in 0.51s
```

Green (Step 13): `20 passed` (42 across both files).

## Verification results (`bash scripts/verify.sh`)

Final run: **exit 0, "All checks passed."** (Windows 11, Docker Desktop 28.5, PostgreSQL 16.15, Mailpit v1.31.3.)

| Gate | Result |
|---|---|
| Backend lint and format (Ruff, incl. `S` and `D`) | All checks passed |
| Backend types (`mypy --strict app`) | No issues in 35 source files |
| Backend layering (import-linter) | 4 contracts kept, 0 broken. A seeded `routes -> tokens` import breaks it |
| Backend tests (`-m "not perf"`, real PostgreSQL, sockets blocked) | **206 passed**; line coverage **97.42%** (floor 80%) |
| Backend latency (p95, 5 warm-up + 50 measured) | register **100.2 ms** (≤ 500), login **110.3 ms** (≤ 500), verify **22.7 ms** (≤ 500), `/auth/me` **8.8 ms** (≤ 100), `/health` **3.0 ms** (≤ 50). All passed on the first run |
| Frontend lint (ESLint, security plugin, layering, `--max-warnings=0`) | Clean. A seeded UI file importing the store, the auth API or the client, calling `fetch` or using `localStorage` produces 9 errors |
| Frontend format and types | Prettier clean; `tsc --noEmit` clean |
| Frontend tests (Vitest + RTL) | **51 passed** (9 files); lines **95.79%**, statements 93.18%, branches 85.65% (floor: lines 80%) |
| Bundle budget (gzipped JS) | `/signup` 191.2 KB, `/login` 189.4 KB, `/verify` 189.7 KB, `/home` 161.1 KB (limit 200 KB) |
| OpenAPI drift | Types up to date |
| Migration round-trip (`app_e2e`) | upgrade → downgrade → upgrade OK; `alembic check` shows no model drift |
| E2E (Playwright, production build, codes from Mailpit, axe WCAG 2.1 AA) | **2 passed** (phone 390×844, desktop 1280×800) |
| Gitleaks (working tree; pinned container) | No leaks found. A seeded `ghp_` token is detected |
| `pip-audit` (uv.lock export, `--require-hashes`) / `pnpm audit --prod --audit-level high` | No known vulnerabilities / none |
| Auth-as-a-service deny-list | OK. A seeded `@supabase/supabase-js` fails it |
| App independence | OK. A seeded `../backend` import fails it |

## Defects found and fixed during the unit

- **SMTP adapter:** `smtplib.data()` returns the final reply without raising, so a 5xx after `DATA` would have counted as sent. It now raises `SMTPDataError`. The message is also serialised with the SMTP policy (CRLF).
- **Frontend `useAuth`:** the selector built a new object on every call inside `useShallow`, which looped renders (React #185) on `/verify`. It now uses per-field selectors and `useMemo`.
- **API client:** an already-aborted external signal was ignored. It now aborts at once.
- **Accessibility:** Sonner's `richColors` success toast measured 4.25:1. It was removed, so toasts use the default dark-on-white style.
- **Bundle size:** the full zod v4 build made the auth routes about 265 KB. The schemas now use `zod/mini`; the auth routes are at most 191.2 KB against the 200 KB budget, which was not relaxed.

## Deviations from the plan

1. **`src/middleware.ts` → `src/proxy.ts`.** Next.js 16 deprecated `middleware.ts` and renamed it `proxy.ts`; the bundled docs say to use proxy. The CSP tests live in `src/lib/config/csp.test.ts`, which the approved unit-test command covers through `src/lib/config`. The `src/middleware.test.ts` filter in that command now matches nothing.
2. **App entry point.** The plan says `app.main:app`; the app is built by the `app.main:create_app` factory (`--factory`), so importing the module never needs configuration. That keeps the tests and the OpenAPI export environment-free.
3. **Repositories timing.** Code and counter queries were added to `repositories.py` in Step 11 (Green), not Step 14, because the OTP service sits above repositories in the import-linter layers. Users and refresh sessions were added in Step 14 as planned.
4. **Email validation.** The schemas use an explicit syntax check instead of `EmailStr`, because `email-validator` rejects the special-use `.test` domain that the approved test data uses (`@example.test`). The `email-validator` dependency was removed.
5. **Gitleaks in CI** runs as the digest-pinned `ghcr.io/gitleaks/gitleaks:v8.28.0` container over the full git history, not `gitleaks/gitleaks-action`. Same tool, pinned, and no licence key needed. Locally, `verify.sh` scans the working tree, because there are no commits yet.
6. **Throwaway CI keys** stay in the step that sources `scripts/ci-env.sh`. Writing to `$GITHUB_ENV` is opt-in (`CI_ENV_EXPORT_TO_GITHUB_ENV=1`). This satisfies both D8 (single source, masked) and "key environment variables scoped to the steps that need them".
7. **`pip-audit`** runs on an export of the committed `uv.lock` (`--require-hashes`). It fails on any known advisory, which is stricter than the high/critical threshold.
8. **Error toasts** use `duration: Infinity` so they stay until dismissed (interaction spec).
9. **Added `scripts/check-app-independence.sh`.** AC1.1.2 and BR8.1 required a cross-import check that was not listed as a script. It runs in CI (security job) and in `verify.sh`.
10. **`localhost` vs `127.0.0.1`.** On Windows, Docker Desktop's IPv6 `localhost` forwarding stalls connections for about 30 s. `ci-env.sh`, `.env.example` and the SMTP default therefore use `127.0.0.1` for PostgreSQL, SMTP and Mailpit. Browser-facing origins stay on `localhost`, because the refresh cookie must be same-site.

## Open items for the skeleton checkpoint

- **Branch protection (AC1.3.2):** apply `docs/branch-protection.md` after the first push. No approving review is required yet (D9).
- **Lighthouse LCP (NFR9.4):** a manual check at the checkpoint (performance design §3).
- **Frontend bundle headroom:** the largest auth route is 191.2 KB of the 200 KB budget. Later units should watch it.
- The Starlette test client warns that `httpx` is deprecated in favour of `httpx2`. This is only a warning, with no effect on results.
