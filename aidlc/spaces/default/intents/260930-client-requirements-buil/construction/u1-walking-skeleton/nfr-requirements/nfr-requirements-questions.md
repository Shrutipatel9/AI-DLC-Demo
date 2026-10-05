# NFR Requirements — U1 Walking Skeleton — Questions

U1 fixes the technical foundation every later unit builds on, so a few technology choices that the earlier stages deliberately deferred land here. The client already fixes FastAPI, SQLAlchemy, Alembic, PostgreSQL, Next.js + TypeScript and Zustand (`NFR-001`–`NFR-006`); the token lifetimes and code limits are fixed by `AUTH-010`–`AUTH-016`.

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — Runtime versions and package managers
A. Python 3.12 managed with `uv`; Node.js 22 LTS with `pnpm` (fast, reproducible lockfiles, current long-term-support versions) (Recommended)
B. Python 3.12 with `pip` + `pip-tools`; Node.js 22 LTS with `npm`
X. Other (please specify)

[Answer]: A

### Question 2 — Database access style (deferred from practices discovery)
A. Synchronous SQLAlchemy 2.0 with a thread pool — simpler for the client's team to maintain, and CPU-heavy face measurement won't block an event loop (Recommended)
B. Async SQLAlchemy 2.0 (asyncpg) throughout
X. Other (please specify)

[Answer]: A

### Question 3 — Password hashing
A. Argon2id (current OWASP first choice) with OWASP-recommended parameters, configurable (Recommended)
B. bcrypt with cost 12
X. Other (please specify)

[Answer]: A

### Question 4 — Signing the access token
There is one backend that both issues and checks tokens.

A. HS256 with a long random secret from configuration (simple; nothing else needs to verify tokens) and a key id so the secret can be rotated (Recommended)
B. An asymmetric key pair (EdDSA or RS256), ready for other services to verify tokens in future
X. Other (please specify)

[Answer]: A

### Question 5 — Throttling the sign-in endpoints
The code rules already limit guessing per account (5 tries, 60 s resend). Nothing yet limits one source hammering sign-up or login across many accounts (review finding R-07).

A. Add a per-IP limit on `/auth/register`, `/auth/login`, `/auth/verify` (for example 20 requests per minute per IP, configurable), returning 429 (Recommended)
B. No extra throttling now; leave it to the hosting layer when hosting is chosen
X. Other (please specify)

[Answer]: A

### Question 6 — Response-time target for the sign-in endpoints
A. 95% of sign-up, login, verify and "who am I" requests answer within 500 ms on a developer machine, not counting email delivery (sending happens after the response is prepared or within the 10 s email timeout); "who am I" within 100 ms (Recommended)
B. No numeric target for this unit
X. Other (please specify)

[Answer]: A
