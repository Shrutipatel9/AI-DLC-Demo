# Unit Test Instructions — U1 Walking Skeleton

## Framework setup

| App | Runner | Configuration | Notes |
|---|---|---|---|
| Backend | pytest + pytest-cov + pytest-socket + httpx (FastAPI `TestClient`) | `backend/pyproject.toml` (`[tool.pytest.ini_options]`: markers `perf`; `--disable-socket --allow-hosts=127.0.0.1,localhost`) and `backend/tests/conftest.py` | Integration tests use real PostgreSQL 16 from Compose (database `app_test`, migrated with Alembic at session start), never SQLite |
| Frontend | Vitest + React Testing Library + jsdom | `frontend/vitest.config.ts` (coverage provider v8, `thresholds.lines: 80`, a global `fetch` stub that fails on any unhandled request) | Component tests render with a fresh Zustand store per test |
| End-to-end | Playwright (Chromium) + `@axe-core/playwright` | `frontend/playwright.config.ts` (projects `phone` 390×844 and `desktop` 1280×800) | Needs Compose `postgres` + `mailpit`, the API on 8000 and the production web build on 3000 |

## Prerequisites

1. `docker compose up -d --wait postgres mailpit`
2. Load the test environment: `source scripts/ci-env.sh`. It sets the database URLs, throwaway signing and code keys, `EMAIL_BACKEND`, the origins and the SMTP settings.
3. `cd backend && uv sync --frozen`; `cd frontend && pnpm install --frozen-lockfile`

## How to run THIS UNIT's tests

All commands below are scoped to U1's test folders and files only.

**Runnable before the first test-first cycle (Step 5)**, from `backend/`:
```bash
uv run pytest tests/identity/test_codes.py tests/identity/test_tokens.py -q
```
Before Steps 10 and 12 this reports that no tests were collected (exit 5 is accepted only at this point). After each Red step it must fail on assertions, not on import or collection errors.

**Backend, U1 unit and integration tests with coverage** (from `backend/`):
```bash
uv run pytest tests/platform tests/identity tests/health -m "not perf" --cov=app --cov-report=term-missing --cov-fail-under=80
```

**Backend, U1 performance checks** (from `backend/`):
```bash
uv run pytest tests/identity/test_perf_auth.py tests/health/test_perf_health.py -m perf -q
```

**Frontend, U1 unit and component tests with coverage** (from `frontend/`):
```bash
pnpm vitest run src/lib/api src/lib/auth src/lib/config src/components/auth src/app src/middleware.test.ts --coverage
```

**End-to-end, U1 skeleton journey** (from `frontend/`, with the API and the production web build running):
```bash
pnpm exec playwright test e2e/skeleton.spec.ts
```

**Migration round-trip** (from `backend/`, against `app_e2e` only):
```bash
uv run alembic -x db=e2e upgrade head && uv run alembic -x db=e2e downgrade base && uv run alembic -x db=e2e upgrade head
```

## Test-first modules and their Red evidence

| Module | Test file | Red run |
|---|---|---|
| OTP service `backend/app/identity/codes.py` | `backend/tests/identity/test_codes.py` | `uv run pytest tests/identity/test_codes.py -q` must fail on assertions before `codes.py` is implemented; the output is pasted into `code-summary.md` |
| JWT service `backend/app/identity/tokens.py` | `backend/tests/identity/test_tokens.py` | `uv run pytest tests/identity/test_tokens.py -q`, the same rule |

All other modules are test-after: implement first, then write and run their tests before the unit is done.

## Expected coverage targets

| Scope | Target | Enforced by |
|---|---|---|
| Backend line coverage (whole `app/`) | ≥ 80% | `--cov-fail-under=80` |
| Frontend line coverage (whole `src/`) | ≥ 80% | Vitest `thresholds.lines: 80` |
| Test volume (Standard strategy) | 5–8 tests per component; about 120 backend and 45 frontend tests in U1 | Plan Steps 9, 16, 20 |
| E2E | 1 journey × 2 viewports, with axe | Not counted toward line coverage |

Coverage exclusions are declared only in committed configuration (`backend/pyproject.toml` `[tool.coverage.report] exclude_lines` for `if TYPE_CHECKING:` and `raise NotImplementedError` in ports; `frontend/vitest.config.ts` excludes `types.gen.ts` and `e2e/`). No exclusion is ever added to make the floor pass.

## Mocking and stubbing guidance

- **Email:** the recording fake `app.platform.email.fake.RecordingEmailSender`, injected through the settings `EMAIL_BACKEND=fake`. Tests read the code it captured, and never call a real provider. SMTP adapter tests use a local stub SMTP server on `127.0.0.1` (`aiosmtpd`, started in a fixture); it can stall or fail on command.
- **Time:** the `FrozenClock` fixture (an injectable `Clock` port). No `time.sleep` in tests; expiry, cooldown and lock tests advance the clock.
- **Randomness:** a codes test may inject a fixed code generator; production uses `secrets.randbelow`.
- **Database:** real PostgreSQL. Each test runs in a transaction that is rolled back. Concurrency tests use separate sessions with committed setup and their own cleanup.
- **Frontend HTTP:** `vi.stubGlobal("fetch", …)` with per-test handlers. Any unhandled request fails the test. Do not mock the API client inside component tests; mock `fetch` beneath it.
- **Network:** pytest-socket blocks every host except localhost, and the frontend fetch stub fails on unknown URLs (NFR8.2, BR8.7).

## Test data management

- **Factories:** `tests/factories.py` provides `make_user(verified=…)` and `issue_code(user, purpose)` through the real services, so stored hashes are always genuine.
- Every test email is unique per test (`f"user-{uuid4().hex[:8]}@example.test"`).
- **Passwords:** a valid one is `"Sunrise2026x"`; invalid cases come from the policy table in the test file. A common-password case uses an entry from the bundled list.
- **E2E:** each run signs up a fresh address (`e2e-<timestamp>@example.test`) and finds its code by recipient in Mailpit. The `app_e2e` database is dropped and recreated before each run.
