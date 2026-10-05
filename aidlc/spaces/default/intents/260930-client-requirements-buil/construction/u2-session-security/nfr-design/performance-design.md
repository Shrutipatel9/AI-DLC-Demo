# Performance Design — U2 Session Security

**Sources:** `nfr-requirements/performance-requirements.md` (NFR9.1–NFR9.8), U1 performance design.

## 1. Latency budgets

| Endpoint | Target | Budget | Main cost |
|---|---|---|---|
| `/auth/refresh` | ≤ 200 ms (NFR9.1) | CSRF check < 1 ms + limiter about 10 ms + locked select/update/insert about 15 ms + JWT < 1 ms | Database round-trips |
| `/auth/logout` | ≤ 200 ms (NFR9.2) | CSRF + limiter + one family update about 10 ms | Database |
| `/auth/resend-code` | ≤ 200 ms (NFR9.3) | limiter + HMAC + counter upsert + code insert about 20 ms; email after the response | Database |
| forgot, verify-code | ≤ 500 ms (NFR9.4) | as above; verify-code adds the locked counter transaction | Database |
| reset, change-password | ≤ 500 ms (NFR9.5) | Argon2id hash about 100 ms (change adds a verify, about 100 ms) + one transaction | Argon2id |

## 2. Techniques
- **Indexes (migration 0002):** `refresh_sessions(family_id)`; a partial index `refresh_sessions(user_id) WHERE revoked_at IS NULL AND rotated_at IS NULL`; `refresh_sessions(parent_token_id)`, for looking up the child on recovery; `password_reset_tokens(token_hash)` unique; `email_attempt_counters(email_hash, purpose)` primary key.
- **Argon2:** runs through `to_thread` (as in U1).
- **Client restore (NFR9.6):** refresh and `/auth/me` run back to back behind the loader. There is no other network call before the home page renders.
- **Cross-tab refresh (NFR9.7):** one network refresh. Waiting tabs adopt the result from the broadcast in under 10 ms.
- **Bundle (NFR9.8):**
  - The coordinator, toast service and dialog add about 6 KB gzipped (no new libraries; `AlertDialog` already ships with shadcn).
  - The forgot, reset and settings pages are separate routes, so they don't load on the auth pages.
  - The size check guards the 200 KB budget.

## 3. Measurement
- **Backend:** the pytest `perf` marker covers the new endpoints: 5 warm-up and 50 measured requests, one re-run.
- **Client timings:** Playwright journey assertions for restore (≤ 1.5 s) and two-tab refresh (≤ 1 s).
- **Bundle:** the existing size check.
