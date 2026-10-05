# Code Summary — U2 Session Security

**Unit:** `u2-session-security` · **Stories:** US11.7, US3.3, US3.5, US3.6, US3.7, US3.9, US3.10, US3.11, US11.5 (36 acceptance criteria).

**Testing contract:** `custom` (team). Three modules were written test-first, each with a recorded Red run before any implementation: the backend session service (`sessions.py`), the backend reset-code flow (`password_reset.py`) and the frontend refresh coordinator (`refresh-coordinator.ts`). Every other layer is test-after.

All application code is at the workspace root (`backend/`, `frontend/`, `scripts/`, `.github/`). Every path U2 created or changed (112, including U1 files) is listed in `source-manifest.json`. Nothing was committed or pushed (D11). No file was deleted.

## What was built

| Area | Where | Notes |
|---|---|---|
| Settings (Step 1) | `backend/app/platform/settings.py`, `.env.example`, `scripts/ci-env.sh` | `REFRESH_TOKEN_DAYS` (replaces U1's `REFRESH_TOKEN_TTL_SECONDS`; the old name is now a derived property), `RESET_TOKEN_MINUTES`, `REFRESH_ATTEMPT_RECOVERY_SECONDS`, `CSRF_ALLOWED_ORIGINS` (normalised; defaults to `FRONTEND_ORIGIN`), `REFRESH_RATE_LIMIT_PER_MINUTE`, `EMAIL_HASH_KEY` (base64, ≥ 32 bytes; the `change-me` placeholder is refused). `REFRESH_COOKIE_PATH` must be `/auth`; `SameSite=none` needs `Secure`. Engine `hide_parameters=True` (D8). `ci-env.sh` generates `EMAIL_HASH_KEY` and raises the test-only limits to 1000 (D10) |
| Migration `0002_u2_session_security` (Step 2) | `backend/alembic/versions/0002_u2_session_security.py`, `app/identity/models.py` | `password_reset_tokens`, `email_attempt_counters`, `verification_attempts.flow_started_at`, `refresh_sessions.revoked_reason` (with checks) and `attempt_hash`, indexes on `parent_token_id` and the partial `user_id` usable index. Clean downgrade; `alembic check` reports no drift |
| Session service (test-first) | `app/identity/sessions.py` | Rotation in a family, strict reuse detection, attempt-id recovery (SHA-256 stored, 22 base64url chars, 60 s, unused child), lock-then-update revocation, parent→child lock order, every branch commits and returns refusals (D1, D2). One retry on a PostgreSQL deadlock |
| Password reset (test-first) | `app/identity/password_reset.py`, `shadow.py`, `delivery.py` | Non-revealing forgot with equal work; shadow counters (HMAC of the email) lock unknown emails like real ones; 256-bit single-use token stored as SHA-256 with an atomic conditional update; reset revokes every session in one transaction. Codes are issued and emailed by a background task with its own DB session; a failed send supersedes only that code id (D3) |
| Resend and lockout | `app/identity/services.py`, `codes.py` | `resend_code`: signup keeps the visible 429s; login and reset are non-revealing and honoured only within 10 minutes of `flow_started_at`. Login checks the lockout only after a correct password (D4). Unknown-email login verify now uses the shadow counter |
| Change password | `app/identity/password_change.py` | Verifies the cookie secret, keeps the cookie's family, revokes every other family (D6) |
| CSRF, CORS, routes | `app/platform/csrf.py`, `middleware.py`, `ratelimit.py`, `routing.py`, `app/identity/routes.py`, `schemas.py`, `cookies.py` | Seven endpoints. CORS outermost with GET/POST/OPTIONS and the extra headers (D7). Refresh and logout: CSRF → refresh limit → handler; every refresh 401 clears the cookie; logout always 204 |
| Logs and metrics | `app/platform/logging.py`, `metrics.py` | Allow-list adds `familyId`, `reason`, `count`, `sent`, `outcome`. New series `auth_refresh_total`, `auth_sessions_revoked_total`, `auth_password_resets_total`, `auth_password_changes_total`. Database exceptions are logged without their message (see Defects) |
| Clean-up command | `app/identity/cleanup.py` | `uv run python -m app.identity.cleanup`; batches of 1,000 with `SKIP LOCKED`; idempotent |
| Refresh coordinator (test-first) | `frontend/src/lib/auth/refresh-coordinator.ts` | Proactive refresh at expiry − 60 s, single flight, Web Lock `auth-refresh`, 5 s adoption window, BroadcastChannel claim fallback (12 s cap), per-tab fallback, 10 s timeout, one retry with the same attempt id, sign-out once, generation guard |
| Store, client, session wiring | `src/lib/auth/{store,session,actions,api,hooks,index,session-log}.ts`, `src/lib/api/{client,errors}.ts` | Status `initializing/signedIn/signedOut`, sign-out reason, generation, restore (refresh → `/auth/me`), logout under the lock. The client retries only `NOT_AUTHENTICATED` once; `apiRaw` for refresh/logout. The reset token stays in module memory (UI only sees `hasResetToken()`) |
| Feedback components | `src/components/feedback/{toast.tsx,confirm.ts,confirm-dialog.tsx}`, `src/components/ui/{toaster,form-field,button}.tsx` | Toast service over Sonner (`role=status` 5 s / `role=alert` persistent, close button, max 3, below the header on phones); `confirm()` with a focus-trapped `alertdialog`; `FieldError` |
| Pages | `src/app/{forgot-password,forgot-password/verify,reset-password,settings/password}`, `home`, `login`, `layout.tsx`; `src/components/{app,auth,settings}/…` | `AuthBootstrap`, `FullPageLoader` (with Retry), `ProtectedRoute`, `UserMenu` (confirm → logout, Change password link), `ResendCodeButton`, `SecurityNotice`, forgot/reset/change forms, all with `data-testid` |
| E2E | `frontend/e2e/session.spec.ts`, `skeleton.spec.ts` | Five session scenarios (four `@checkpoint`) plus axe on the dialog, a toast and the new pages. The skeleton journey now checks "reload keeps me" and a confirmed logout |
| Scripts and CI | `scripts/verify-skeleton.sh`, `verify.sh`, `.github/workflows/ci.yml`, `frontend/scripts/size-check.mjs` | Checkpoint subset at desktop with the 110 s guard (D9); full matrix in `verify.sh` and CI; the perf step includes the U2 latency and timing files; the size check covers the four new routes |
| Docs | `backend/README.md`, `frontend/README.md` | New settings, the clean-up command, the session model, the coordinator and the feedback components |

## Red evidence (test-first modules)

Each Red run executed against an interface-only module (signatures and types; bodies raise `NotImplementedError` / "not implemented"). Every test was collected; none failed on import or collection.

### Session service — `uv run pytest tests/identity/test_sessions.py -q` (Step 4)

```text
FAILED tests/identity/test_sessions.py::test_start_stores_only_the_id_and_a_hash_of_the_secret
FAILED tests/identity/test_sessions.py::test_refresh_rotates_into_the_same_family_with_a_new_cookie_and_access_token
FAILED tests/identity/test_sessions.py::test_second_exchange_of_a_rotated_session_revokes_the_whole_family
FAILED tests/identity/test_sessions.py::test_a_session_works_until_seven_days_and_is_expired_at_seven_days
FAILED tests/identity/test_sessions.py::test_missing_malformed_unknown_or_wrong_cookies_are_invalid_and_change_nothing[missing]
FAILED tests/identity/test_sessions.py::test_missing_malformed_unknown_or_wrong_cookies_are_invalid_and_change_nothing[empty]
FAILED tests/identity/test_sessions.py::test_missing_malformed_unknown_or_wrong_cookies_are_invalid_and_change_nothing[no-dot]
FAILED tests/identity/test_sessions.py::test_missing_malformed_unknown_or_wrong_cookies_are_invalid_and_change_nothing[no-secret]
FAILED tests/identity/test_sessions.py::test_missing_malformed_unknown_or_wrong_cookies_are_invalid_and_change_nothing[bad-id]
FAILED tests/identity/test_sessions.py::test_missing_malformed_unknown_or_wrong_cookies_are_invalid_and_change_nothing[bad-secret]
FAILED tests/identity/test_sessions.py::test_missing_malformed_unknown_or_wrong_cookies_are_invalid_and_change_nothing[unknown]
FAILED tests/identity/test_sessions.py::test_missing_malformed_unknown_or_wrong_cookies_are_invalid_and_change_nothing[wrong]
FAILED tests/identity/test_sessions.py::test_secret_comparison_is_constant_time
FAILED tests/identity/test_sessions.py::test_a_revoked_session_is_refused_as_revoked
FAILED tests/identity/test_sessions.py::test_attempt_ids_must_be_22_base64url_characters_and_are_stored_hashed
FAILED tests/identity/test_sessions.py::test_lost_response_is_recovered_with_the_same_attempt_id
FAILED tests/identity/test_sessions.py::test_any_other_replay_of_a_rotated_session_is_reuse[different-id]
FAILED tests/identity/test_sessions.py::test_any_other_replay_of_a_rotated_session_is_reuse[no-id]
FAILED tests/identity/test_sessions.py::test_any_other_replay_of_a_rotated_session_is_reuse[malformed-id]
FAILED tests/identity/test_sessions.py::test_any_other_replay_of_a_rotated_session_is_reuse[after-60s]
FAILED tests/identity/test_sessions.py::test_any_other_replay_of_a_rotated_session_is_reuse[used]
FAILED tests/identity/test_sessions.py::test_a_child_created_without_an_attempt_id_is_never_recoverable
FAILED tests/identity/test_sessions.py::test_logout_with_a_rotated_cookie_revokes_the_live_child
FAILED tests/identity/test_sessions.py::test_logout_without_a_usable_cookie_still_succeeds[None]
FAILED tests/identity/test_sessions.py::test_logout_without_a_usable_cookie_still_succeeds[]
FAILED tests/identity/test_sessions.py::test_logout_without_a_usable_cookie_still_succeeds[garbage]
FAILED tests/identity/test_sessions.py::test_logout_without_a_usable_cookie_still_succeeds[9c342db4-b129-48e7-8733-7e6da18b9c8d.AAAA]
FAILED tests/identity/test_sessions.py::test_logout_with_a_wrong_secret_revokes_nothing
FAILED tests/identity/test_sessions.py::test_current_family_needs_the_right_secret_and_the_same_user
FAILED tests/identity/test_sessions.py::test_revoke_user_sessions_keeps_only_the_named_family
FAILED tests/identity/test_sessions.py::test_two_parallel_refreshes_of_one_cookie_give_one_child_and_one_reuse
FAILED tests/identity/test_sessions.py::test_two_parallel_refreshes_with_the_same_attempt_id_give_one_child_and_one_reissue
FAILED tests/identity/test_sessions.py::test_logout_racing_a_refresh_leaves_no_usable_session
33 failed, 1 warning in 1.21s
```

A first attempt errored in a fixture (the `cookie` fixture called the unimplemented `start()`), so the cookie was moved into each test body before the recorded run. Green (Step 5): `33 passed` on the first implementation run; four defensive-branch tests were added while green (`sessions.py` at 100% lines).

### Password reset — `uv run pytest tests/identity/test_password_reset.py -q` (Step 6)

```text
FAILED tests/identity/test_password_reset.py::test_request_gives_the_same_reply_for_real_unknown_cooldown_and_locked_emails
FAILED tests/identity/test_password_reset.py::test_request_records_the_flow_start_and_reserves_the_cooldown
FAILED tests/identity/test_password_reset.py::test_unknown_emails_use_a_keyed_shadow_counter_and_never_store_the_email
FAILED tests/identity/test_password_reset.py::test_a_verified_code_yields_a_256_bit_token_stored_only_as_a_hash
FAILED tests/identity/test_password_reset.py::test_a_new_token_makes_earlier_unused_tokens_unusable
FAILED tests/identity/test_password_reset.py::test_wrong_codes_count_down_and_the_fifth_locks_for_fifteen_minutes
FAILED tests/identity/test_password_reset.py::test_unknown_emails_lock_after_five_exactly_like_real_accounts
FAILED tests/identity/test_password_reset.py::test_a_code_is_expired_at_ten_minutes
FAILED tests/identity/test_password_reset.py::test_a_login_code_never_verifies_for_reset
FAILED tests/identity/test_password_reset.py::test_reset_token_works_at_nine_fifty_nine_and_not_at_ten
FAILED tests/identity/test_password_reset.py::test_unknown_tokens_are_refused[]
FAILED tests/identity/test_password_reset.py::test_unknown_tokens_are_refused[short]
FAILED tests/identity/test_password_reset.py::test_unknown_tokens_are_refused[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx]
FAILED tests/identity/test_password_reset.py::test_unknown_tokens_are_refused[not a token at all]
FAILED tests/identity/test_password_reset.py::test_a_reset_token_works_once
FAILED tests/identity/test_password_reset.py::test_a_weak_password_is_refused_and_the_token_stays_usable
FAILED tests/identity/test_password_reset.py::test_reset_sets_the_password_and_revokes_every_session
FAILED tests/identity/test_password_reset.py::test_a_failure_inside_the_reset_leaves_no_partial_state
FAILED tests/identity/test_password_reset.py::test_two_concurrent_resets_with_one_token_give_exactly_one_success
FAILED tests/identity/test_password_reset.py::test_a_reset_racing_a_refresh_leaves_no_usable_session
FAILED tests/identity/test_password_reset.py::test_reply_type - NotImplemente...
21 failed, 1 warning in 1.39s
```

Green (Step 7): `21 passed`; three branch tests added while green (`password_reset.py` and `shadow.py` at 100%).

### Refresh coordinator — `pnpm vitest run src/lib/auth/refresh-coordinator.test.ts` (Step 13)

```text
     × refreshes once, one minute before the access token expires, and not before 20ms
     × shares one refresh between concurrent callers in a tab 2ms
     × three concurrent 401s make one refresh call and each request is retried once 8ms
     × does not retry a retried request that gets 401 again 2ms
     × a refresh that answers 401 starts no further refresh and the request fails 2ms
     × a refresh 401 signs out once and rejects every waiter 1ms
     × maps the server reason to the sign-out reason 2ms
     × retries once with the same attempt id after a network error, then recovers 1ms
     × after a second network error or 5xx the waiters fail, one error is shown, the user stays 1ms
     × a hung refresh times out after 10 s, is retried once, and always releases the lock 5ms
     × two tabs refreshing together make one network call; the second adopts the result 2ms
     × a broadcast received more than 5 s ago is not adopted 1ms
     × an idle tab applies a newer broadcast at once and ignores an older one 5ms
     × a signedOut broadcast signs this tab out once with the sender's reason 2ms
     × a refresh 401 tells the other tabs to sign out too 1ms
     × logout waits for the lock, bumps the generation, calls the server and tells other tabs 1ms
     × logout still tells other tabs when the server call fails 1ms
     × a late refresh result never revives a tab that was signed out meanwhile 1ms
     × without Web Locks, a BroadcastChannel claim lets one tab refresh and the other adopt 1ms
     × a claim loser that hears nothing within 12 s refreshes by itself 6ms
     × without locks or broadcast, each tab refreshes on its own 2ms
     × attempt ids are 22 random base64url characters 1ms
 Test Files  1 failed (1)
      Tests  22 failed | 2 passed (24)
```

The two that passed against the stub are negative assertions ("re-schedules … and cancels with null" and "only NOT_AUTHENTICATED triggers a refresh"): a do-nothing stub satisfies "no refresh happens". Green (Step 14): 24 passed after two test corrections: one tab lacked a lock and so used the 150 ms claim path that the test never advanced; and the claim-loser test assumed which tab wins, although claim ids are random. A 25th test (timer overflow) was added later (see Defects).

## Verification results

### `bash scripts/verify.sh` — exit 0, "All checks passed.", 5 min 20 s (real 5m19.6s)

| Gate | Result |
|---|---|
| Backend lint/format (Ruff incl. `S`, `D`), `mypy --strict app`, import-linter | Clean; no issues in 42 files; 4 contracts kept (extended for the new modules) |
| Backend tests (real PostgreSQL, sockets blocked) | **362 passed** (206 U1 + 156 U2); line coverage **98%** (TOTAL 2902 stmts, 63 missed; floor 80%) |
| Backend latency p95 (5 warm-up + 50) | refresh **66.4 ms** (≤ 200), logout **37.7** (≤ 200), resend-code **26.4** (≤ 200), forgot **38.4** (≤ 500), verify-code **35.1** (≤ 500), reset **89.8** (≤ 500), change-password **142.3** (≤ 500). U1: register 325.5, login 87.6, verify 32.2, me 16.6, health 3.0. All on the first run |
| Anti-enumeration timing (`forgot`, 200 samples per branch) | medians: real 18.0, unknown 14.2, cooldown 16.4, locked 16.4 ms; p95: 23.0 / 19.6 / 21.9 / 22.0 ms. **Median spread 3.8 ms, p95 spread 3.3 ms** (< 50 ms) |
| Frontend lint (`--max-warnings=0`), Prettier, `tsc --noEmit` | Clean |
| Frontend tests (Vitest + RTL) | **142 passed** (20 files; 51 U1 + 91 U2); lines **95.13%**, statements 92.85%, branches 86.3%, functions 94.04% (floor: lines 80%) |
| Bundle budget (gzipped JS) | `/signup` 195.1, `/login` 193.6, `/verify` 194.1, `/home` 165.5, `/forgot-password` 193.2, `/forgot-password/verify` 194.1, `/reset-password` 195.0, `/settings/password` **196.1 KB** (limit 200 KB) |
| OpenAPI drift | Types up to date |
| Migration round-trip (`app_e2e`, 0001 + 0002) | upgrade → downgrade → upgrade OK |
| E2E (Playwright, production build, Mailpit, axe WCAG 2.1 AA) | **12 passed** (skeleton + 5 session scenarios × phone and desktop) |
| Gitleaks / pip-audit / pnpm audit / deny-list / app independence | No leaks / no known vulnerabilities / none / OK / OK |

Earlier runs in this step failed and were fixed (never by relaxing a gate): a literal `\n` I had written into the perf command line; Prettier on the longer skeleton title; a Gitleaks generic-api-key false positive on a test line (the line was restructured; the allow-list was not widened); and a blank line between import groups in `app/platform/middleware.py` that went missing while a run was starting (not from my commands; restored with Ruff). One run needed the U1 automatic perf re-run for change-password (713 ms, then 240 ms) under load; the final run met every target on the first run.

### `bash scripts/verify-skeleton.sh` — exit 0, **48 s** (budget 110 s)

Fresh `app_e2e`, migration round-trip, API + production build, Playwright at desktop: `5 passed (23.8s)` — the skeleton journey and the four `@checkpoint` session scenarios (reload ≤ 1.5 s; two tabs both valid ≤ 1 s; logout in one tab signs out the other; forgot → Mailpit code → reset → log in). An earlier run on this machine took 55 s. The first attempts were blocked by a stale `next start` (port 3000) and a stale `uvicorn app.main:app --reload` (port 8000) left from 2026-10-01; both were this repository's own processes and were stopped.

## Defects found and fixed during the unit

- **Database errors could still log personal data (NFR3.2).** `hide_parameters=True` hides SQLAlchemy's parameter list, but PostgreSQL's own `DETAIL` line repeats the key value (for example the email in a unique violation). The JSON formatter now renders database exceptions as stack + class + SQLSTATE, "details hidden". A test forces a duplicate-email integrity error and checks the formatted log.
- **Proactive-refresh timer overflow.** `setTimeout` fires at once for delays above 2³¹−1 ms, so a far-future expiry refreshed immediately. Real tokens last 15 minutes, but the coordinator now clamps the delay; a regression test covers it.
- **Race-test ordering.** The "logout/reset/change racing a refresh" tests could start the revocation before the refresh held its row lock (rare flake). They now wait until the refresh holds the lock; stable over 15 repetitions.
- **Restore vs a new sign-in.** A sign-in now starts a new store generation, so a restore still in flight cannot sign out a user who has just verified a code; a restore that ends while a code step is open keeps that step.

## Deviations from the plan

1. **`REFRESH_TOKEN_DAYS` replaces `REFRESH_TOKEN_TTL_SECONDS`.** One source of truth; `refresh_token_ttl_seconds` remains as a derived property, so U1 code and tests are unchanged.
2. **Migration FK change is a no-op.** `parent_token_id ON DELETE SET NULL` already existed in 0001; 0002 documents this.
3. **Confirmation dialog is built in-house, not on shadcn `AlertDialog`.** `@radix-ui/react-alert-dialog` is not installed and would add a dependency against about 9 KB of bundle headroom (tech-stack: no new runtime dependency). The custom `alertdialog` meets every NFR9.9 clause and passes axe; the largest route is 196.1 KB.
4. **Toasts use `sonner.custom`.** Sonner sets no per-toast role, so the service renders its own content with `role="status"`/`role="alert"` and a close button. U1 forms and their test mocks moved to `@/components/feedback/toast`.
5. **`resetPassword(newPassword)` instead of `resetPassword(token, newPassword)`.** The reset token stays in `lib/auth` memory, so UI code never handles a token (FE-007).
6. **Sign-out reason `password_changed` added** to show R-03's "Your password was changed" message distinctly from the security message.
7. **Restore notices.** A restore that finds no valid cookie (`INVALID`/`EXPIRED`) records no reason, so first-time visitors see no "session ended" notice; `REUSE_DETECTED`/`REVOKED` always set `security` (WF-U2-2 step 4).
8. **Refresh deadlock retry.** A replayed-session refresh (parent → child locks) and a scope revocation (`token_id` order) can deadlock in rare races; the losing transaction is rolled back and re-run once (`with_deadlock_retry`). Tested with an injected `DeadlockDetected`.
9. **Background issuance uses `CodeService.issue(..., cooldown_reserved=True)`** (backward-compatible keyword), because the request already reserved the 60 s slot.
10. **U1 behaviour U2 replaces.** U1 tests that encoded "reload signs out", local-only sign-out and the "start again" link were updated; the skeleton e2e journey now checks "reload keeps me" and a confirmed logout before logging in again.
11. **Size check widened** to the four new routes (stricter, not looser).
12. **`test-utils.ts`** (fake locks and broadcast) lives in `src/lib/auth/` as the instructions specify and is counted in coverage.

## Open items

- **NFR5.1 Playwright variant.** "Network errors never sign out" is covered by Vitest (coordinator and store with failing fetch / 5xx); a Playwright run with the API stopped mid-session was not added.
- **Branch protection and CI on GitHub** are unchanged from U1 and still apply after the first push (nothing is committed).
- **Bundle headroom** is now about 4 KB on `/settings/password`; later units should watch it.
- The Starlette test client still warns that `httpx` is deprecated in favour of `httpx2` (no effect on results).
