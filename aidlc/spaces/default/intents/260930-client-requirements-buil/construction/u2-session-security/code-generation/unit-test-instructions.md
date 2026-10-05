# Unit Test Instructions — U2 Session Security

## Framework setup

U2 uses U1's runners and configuration unchanged:
- **Backend:** pytest + pytest-cov + pytest-socket against real PostgreSQL (`app_test`), with the `FrozenClock` and the recording email fake.
- **Frontend:** Vitest + React Testing Library with jsdom.
- **End-to-end:** Playwright with axe.

U2 adds three test fixtures:

| Fixture | Where | Purpose |
|---|---|---|
| `two_sessions` | `backend/tests/identity/conftest.py` | Opens two independent database sessions with committed setup, for the refresh, logout, reset and change race tests (cleans up after itself) |
| `fakeLocks` / `fakeBroadcast` | `frontend/src/lib/auth/test-utils.ts` | Deterministic in-memory `navigator.locks` and `BroadcastChannel` shared by simulated tabs. Each can be removed to test the fallback paths |
| `sessionCookie(...)` | `backend/tests/factories.py` | Issues a real refresh session for a user, returning the cookie value and the ids |

## Prerequisites
1. `docker compose up -d --wait postgres mailpit`
2. `source scripts/ci-env.sh`. This also sets `EMAIL_HASH_KEY` and the test-only rate limits.
3. `cd backend && uv sync --frozen`, and `cd frontend && pnpm install --frozen-lockfile`.

## How to run THIS UNIT's tests

All commands below are limited to U2's test files.

**Runnable before the first test-first cycle (Step 3).**

From `backend/`:
```bash
uv run pytest tests/identity/test_sessions.py tests/identity/test_password_reset.py -q
```
From `frontend/`:
```bash
pnpm vitest run src/lib/auth/refresh-coordinator.test.ts
```
Before Steps 4, 6 and 13, these report that no tests were collected. That is accepted only at this point. After each Red step they must fail on assertions, never on import or collection errors.

**Backend, U2 tests** (from `backend/`):
```bash
uv run pytest tests/identity/test_sessions.py tests/identity/test_password_reset.py tests/identity/test_resend_lockout.py tests/identity/test_change_password.py tests/identity/test_csrf_cors.py tests/identity/test_session_routes.py tests/identity/test_cleanup.py tests/identity/test_u2_logs_metrics.py tests/platform/test_settings_u2.py -m "not perf" -q
```

**Backend, U2 performance and anti-enumeration timing** (from `backend/`):
```bash
uv run pytest tests/identity/test_perf_sessions.py tests/identity/test_perf_enumeration.py -m perf -q
```

**Whole-app coverage gate** (it includes U2 code), from `backend/`:
```bash
uv run pytest tests -m "not perf" --cov=app --cov-fail-under=80 -q
```

**Frontend, U2 tests** (from `frontend/`):
```bash
pnpm vitest run src/lib/auth/refresh-coordinator.test.ts src/lib/auth/store.u2.test.ts src/lib/api/client.u2.test.ts src/components/feedback src/components/auth/resend-code-button.test.tsx src/components/auth/forgot-password-form.test.tsx src/components/auth/reset-password-form.test.tsx src/components/settings src/components/app/protected-route.test.tsx src/components/auth/security-notice.test.tsx
```

**Whole-app frontend coverage gate**, from `frontend/`:
```bash
pnpm vitest run --coverage
```

**End-to-end, U2 session journey** (from `frontend/`, with the API and the production web build running):
```bash
pnpm exec playwright test e2e/session.spec.ts
```

**Migration round-trip including `0002`** (from `backend/`, against `app_e2e`):
```bash
uv run alembic -x db=e2e upgrade head && uv run alembic -x db=e2e downgrade base && uv run alembic -x db=e2e upgrade head
```

## Test-first modules and their Red evidence

| Module | Test file | Red run |
|---|---|---|
| `backend/app/identity/sessions.py` | `backend/tests/identity/test_sessions.py` | `uv run pytest tests/identity/test_sessions.py -q` must fail on assertions before the implementation; the output goes into `code-summary.md` |
| `backend/app/identity/password_reset.py` | `backend/tests/identity/test_password_reset.py` | `uv run pytest tests/identity/test_password_reset.py -q`, same rule |
| `frontend/src/lib/auth/refresh-coordinator.ts` | `frontend/src/lib/auth/refresh-coordinator.test.ts` | `pnpm vitest run src/lib/auth/refresh-coordinator.test.ts`, same rule |

## Expected coverage targets

| Scope | Target | Enforced by |
|---|---|---|
| Backend line coverage (whole `app/`) | ≥ 80% (U1 is at 97%; expect at least 95% after U2) | `--cov-fail-under=80` |
| Frontend line coverage (whole `src/`) | ≥ 80% (U1 is at 96%) | Vitest `thresholds.lines: 80` |
| Volume (Standard) | 5–8 tests per component: about 90 new backend tests and 60 new frontend tests | Plan Steps 4, 6, 12, 13, 17 |
| E2E | Session spec at 2 viewports in CI; the `@checkpoint` subset at desktop in the checkpoint command | Not counted toward line coverage |

## Mocking and stubbing guidance
- **Time:** use `FrozenClock` (backend) and `vi.useFakeTimers()` (frontend). Never use real sleeps.
- **Concurrency:**
  - Backend race tests use the `two_sessions` fixture with real row locks and threads. Each test is bounded by a 10 s timeout.
  - Frontend cross-tab tests create two store instances sharing `fakeLocks` and `fakeBroadcast`.
- **HTTP (frontend):** stub `fetch` per test. An unhandled request fails the test. Never mock the coordinator inside the store tests; mock `fetch` beneath it.
- **Email:** use the recording fake. Background tasks run synchronously in `TestClient`, and the tests assert the fake's captured messages.
- **Network:** backend sockets are blocked except localhost (U1).

## Test data management
- Use the factories `make_user`, `issue_code` and `sessionCookie`.
- Give every test a unique email: `user-<hex>@example.test`.
- The valid password is `Sunrise2026x` and the new password is `Moonrise2027y`.
- E2E creates fresh accounts per scenario and reads codes from Mailpit by recipient. The `app_e2e` database is recreated per run.
