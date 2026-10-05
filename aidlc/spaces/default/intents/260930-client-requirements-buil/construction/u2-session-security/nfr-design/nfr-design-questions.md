# NFR Design — U2 Session Security — Questions

The NFR requirements and the post-review notes already settle the patterns: the row-locked refresh exchange, attempt-id recovery, the email sent after the response, shadow counters and the Web Locks coordinator. One operational choice remains.

Pick one letter (or X and describe your own answer).

---

### Question 1 — Running the session clean-up
Old refresh sessions, used reset tokens and idle shadow counters need deleting (NFR11.3). There is no host or scheduler yet.

A. Ship an idempotent `auth-cleanup` command (`uv run python -m app.identity.cleanup`) that a host's scheduler can run daily. Until a host exists it is run manually, and it is documented in the backend README (Recommended)
B. Also run the clean-up automatically inside the API once a day (a background loop in the web process)
X. Other (please specify)

[Answer]: A
