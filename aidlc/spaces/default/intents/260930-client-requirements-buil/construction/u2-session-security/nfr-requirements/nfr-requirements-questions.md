# NFR Requirements — U2 Session Security — Questions

U2 inherits all of U1's foundations: Argon2id, HS256 with `kid`, per-IP throttling, JSON logs, the email budget and 80% coverage. Two quality targets are new for this unit.

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — Response-time targets for the new endpoints
A. For 95% of requests: refresh, logout and resend-code within 200 ms; forgot-password, verify-code, reset and change-password within 500 ms, because they hash a password or send a code. On a developer machine, email delivery excluded (Recommended)
B. Reuse U1's 500 ms for every endpoint
X. Other (please specify)

[Answer]: A

### Question 2 — Record of security events
Security events include: a session family revoked for reuse, a lockout, a password reset or change, and all other sessions signed out.

A. Structured log events only, at WARN or INFO with the user id and no secrets. A user-visible "security history" screen is not in the client document, so it isn't built (Recommended)
B. Also store them in a database table for a future security-history screen
X. Other (please specify)

[Answer]: A
