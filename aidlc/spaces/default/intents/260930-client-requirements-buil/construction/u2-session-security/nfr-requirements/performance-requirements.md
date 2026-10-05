# Performance Requirements — U2 Session Security

**Sources:** answer Q1 in `nfr-requirements-questions.md`. The client sets no auth latency targets. These targets are **[Decided by delivery team — NFR Q6 (U1) and Q1 (U2)]** and filed under NFR9, the same parent used in U1.

**Measurement conditions:** the same as U1.
- Local Compose, warm process.
- 5 warm-up requests, then 50 measured requests per endpoint.
- Email excluded: the recording fake is used, and on the non-revealing endpoints the send happens after the response.

| ID | Metric | Target (p95) | Notes |
|---|---|---|---|
| NFR9.1 | `POST /auth/refresh` | ≤ 200 ms | Row-locked exchange plus JWT signing |
| NFR9.2 | `POST /auth/logout` | ≤ 200 ms | Family revoke |
| NFR9.3 | `POST /auth/resend-code` | ≤ 200 ms | HMAC plus counter upsert; email after the response |
| NFR9.4 | `POST /auth/password/forgot` and `POST /auth/password/verify-code` | ≤ 500 ms | Code hashing; email after the response |
| NFR9.5 | `POST /auth/password/reset` and `POST /auth/change-password` | ≤ 500 ms | One Argon2id hash (change: two — verify current, hash new) |
| NFR9.6 | **Session restore on reload:** time from navigation to the signed-in home content (Playwright, local, production build) | ≤ 1.5 s | Refresh + `/auth/me` behind the loader |
| NFR9.7 | **Cross-tab refresh with two tabs:** wall time until both tabs hold a valid token | ≤ 1 s | One network refresh plus a broadcast |
| NFR9.8 | **Bundle size:** auth routes, including the new session code | ≤ 200 KB gzipped (U1 budget; U1 left about 9 KB of headroom) | New code is shared via the store chunk; heavy libraries are not allowed |

**How it is checked:**
- NFR9.1–NFR9.5: the pytest `perf` marker, as in U1, with one automatic re-run per target.
- NFR9.6–NFR9.7: Playwright timing assertions in the session journey.
- NFR9.8: the existing size check.
