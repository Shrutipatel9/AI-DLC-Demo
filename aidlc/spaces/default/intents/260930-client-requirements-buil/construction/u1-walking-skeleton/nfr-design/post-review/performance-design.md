# Performance Design — U1 Walking Skeleton

**Sources:** `nfr-requirements/performance-requirements.md` (NFR9.1–NFR9.5) and `security-requirements.md` (Argon2id parameters, NFR2.2).

## 1. Latency budgets (p95, local Compose)

| Endpoint | Target | Budget breakdown | Main cost |
|---|---|---|---|
| `POST /auth/register` | ≤ 500 ms (NFR9.1) | limiter 10 ms + policy check under 1 ms + Argon2 hash about 100 ms + tx1 about 15 ms + email excluded | Argon2id |
| `POST /auth/login` | ≤ 500 ms (NFR9.1) | limiter 10 ms + lookup 5 ms + Argon2 verify about 100 ms + tx1 about 15 ms | Argon2id |
| `POST /auth/verify` | ≤ 500 ms (NFR9.1) | limiter 10 ms + locked tx about 20 ms + JWT sign under 1 ms | Database round-trips |
| `GET /auth/me` | ≤ 100 ms (NFR9.2) | JWT verify under 1 ms + primary-key lookup about 3 ms | Database |
| `GET /health` | ≤ 50 ms (NFR9.3) | No I/O | — |

**"Email excluded":** the perf test uses the recording fake. With a real provider, send time adds to the response, within the 25 s reliability budget (NFR5.3). The sign-up and login forms show a busy state, so the user sees progress.

## 2. Techniques
- **Connection pooling:** SQLAlchemy `QueuePool`: `pool_size=5`, `max_overflow=5`, `pool_timeout=5`, `pool_pre_ping=True`, `pool_recycle=1800`. All values come from settings.
- **Indexes (U1 migration):**
  - `users(lower(email))` unique;
  - `one_time_codes(user_id, purpose) WHERE consumed_at IS NULL AND superseded_at IS NULL`;
  - `verification_attempts` primary key `(user_id, purpose)`;
  - `refresh_sessions(token_id)` unique;
  - `rate_limit_hits(key, hit_at)`.
- **Argon2 in the thread pool:** hashing runs through `anyio.to_thread.run_sync` (the default limiter), so it never blocks the event loop. Email sends use their own limiter (reliability design §2). The parameters stay at the OWASP minimum, which keeps the hash at about 100 ms on a laptop core.
- **No caching:** there is nothing worth caching in U1. `/auth/me` is a single primary-key read. This decision is revisited for read-heavy report endpoints (U8).
- **Frontend:** the auth pages are small client components. Fonts are self-hosted via `next/font`; no third-party scripts; shadcn components are imported per component. Pages render per request for the CSP nonce (NFR design Q3). The cost is about 10–30 ms of server render, which is well inside the LCP budget (NFR9.4).

## 3. Measurement design
- **Backend:** pytest marker `perf` (excluded from the default run, included in `make verify`). It runs 5 warm-up and 50 measured requests per endpoint through the ASGI app against the test database, computes p95 with `statistics.quantiles` and asserts the targets. With 50 samples, p95 is less noisy than the 10 named in the requirements; this is stricter, not looser.
- **Frontend:** `pnpm build` prints the route sizes. A small script reads `.next/build-manifest.json` and fails over 200 KB gzipped for the auth routes (NFR9.5). Lighthouse (mobile preset) runs manually at the skeleton checkpoint, and the result is recorded in Build and Test (NFR9.4).
- **Accessibility and viewports:** `@axe-core/playwright` in the journey, with two Playwright projects (390×844 and 1280×800) (NFR9.6, NFR9.7).
