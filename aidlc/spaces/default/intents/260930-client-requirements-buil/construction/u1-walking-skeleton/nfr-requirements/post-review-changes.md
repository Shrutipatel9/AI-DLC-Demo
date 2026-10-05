# Post-Review Changes — NFR Requirements, U1 Walking Skeleton

The requirement files in this folder are kept exactly as the architecture reviewer saw them (review iteration 1, verdict READY; `reviews/review-01.md`). The changes below came from that review's findings. They were made after the review, so they live here rather than in the reviewed files. The human chose this arrangement on 2026-10-01. The NFR design, infrastructure design and code all implement these changes, and the code review checked them in the code.

| Finding | Change | Affects |
|---|---|---|
| R-01 | The public allow-list adds `/health/ready`. `/metrics` is the single token-exempt operational route: off by default and limited to an allow-list. The route-enumeration test also expects `/metrics` to return 404 when disabled and 403 from outside the allow-list. A STRIDE row covers `/metrics` disclosure | NFR2.8, threat model |
| R-02 | **New NFR5.13.** The email send never runs inside a database transaction or while holding a pooled connection or row lock. The order is commit, then send, then compensate in a second short transaction. Test: during a slow send, verify and `/auth/me` still answer within their targets | `reliability-requirements.md` |
| R-03 | NFR2 is partial in U1. Refresh rotation and family revocation, the cookie endpoints with their CSRF defence, resend and password reset are deferred to U2. U1 has no cookie-reading endpoint, so it has no CSRF surface | NFR2 coverage |
| R-04 | The per-IP limiter records each hit in its own short transaction, so rejected or rolled-back requests still count. Old window rows are pruned | NFR2.9 |
| R-05 | Global cap on code emails, `AUTH_EMAIL_HOURLY_CAP` (default 500 per hour). Over the cap: 503 `UPSTREAM_UNAVAILABLE` and a WARN log `auth.email_cap_reached` | threat model (email bombing) |
| R-06 | Code HMAC input is `userId:purpose:code`, compared in constant time (`hmac.compare_digest`) | NFR2.5 |
| R-07 | Delivery-team extensions are noted per parent: NFR5.6–NFR5.12 under NFR5, NFR9.1–NFR9.5 under NFR9, NFR11.1–NFR11.5 under NFR11. Each ID's file is listed in `../nfr-design/traceability.json` | traceability |
| R-08 | Each attempt's timeout is the lesser of 10 s and the remaining 25 s budget. No new attempt starts with under 2 s remaining | NFR5.1, NFR5.3 |
| R-09 | `Strict-Transport-Security: max-age=31536000; includeSubDomains` on the API and frontend outside development | NFR2.13 |
