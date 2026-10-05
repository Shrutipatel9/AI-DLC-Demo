# Performance Requirements — U1 Walking Skeleton

**Sources:** answer Q6 in `nfr-requirements-questions.md`. The client and the inception requirements set no latency targets for sign-in (the only inception timing target is NFR4, analysis time). These targets are new, **[Decided by delivery team — NFR Q6]**, and filed under NFR9 (experience on supported phones and desktops) as their closest inception parent.

**Measurement conditions:**
- the local Docker Compose environment on a developer machine (no hosting chosen, `NFR-010`);
- a warm process;
- 10 sequential requests per endpoint after 5 warm-up requests;
- email delivery excluded: the fake or mail catcher is used, and real-provider latency counts against the 10-second email timeout instead.

| ID | Metric | Target | Percentile | Notes |
|---|---|---|---|---|
| NFR9.1 | `POST /auth/register`, `/auth/login`, `/auth/verify` server response time | ≤ 500 ms | p95 | Dominated by Argon2id (~50–150 ms at the chosen parameters) |
| NFR9.2 | `GET /auth/me` server response time | ≤ 100 ms | p95 | One indexed lookup |
| NFR9.3 | `GET /health` | ≤ 50 ms | p95 | No database call |
| NFR9.4 | Sign-up, login and code pages: Largest Contentful Paint on a mid-range phone profile (Lighthouse "Moto G Power", throttled 4G) | ≤ 2.5 s | Lighthouse single run, median of 3 | Static pages; checked once at the checkpoint |
| NFR9.5 | Frontend JavaScript for the auth pages | ≤ 200 KB compressed | — | Next.js build output report |

**Resource limits:**
- Request bodies on `/auth/*` are capped at 16 KB.
- The database connection pool defaults to 5 connections plus 5 overflow (configurable).

**How it's checked:** a small timing test (pytest marker `perf`, not part of the coverage gate) records p95 for NFR9.1–NFR9.3 and fails over target. The Lighthouse check for NFR9.4–NFR9.5 runs at the checkpoint and its result is recorded in Build and Test.

**Out of scope:** load testing and concurrency targets. There is no hosting yet; this is re-addressed in the Operation phase (not in this workflow).
