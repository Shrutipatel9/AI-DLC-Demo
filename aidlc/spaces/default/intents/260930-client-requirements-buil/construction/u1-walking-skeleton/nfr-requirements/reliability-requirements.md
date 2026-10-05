# Reliability Requirements — U1 Walking Skeleton

**Sources:**
- `requirements.md` NFR5 (reliability of external calls) and NFR12 (email delivery);
- contract C10 / §6 (timeouts and retries);
- the construction guardrails (errors at integration boundaries, no silent failures).

There is no hosting, so availability SLOs are deferred to the Operation phase (outside this workflow).

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR5.1 | Every call to the email provider has a 10 s timeout and up to 2 retries with exponential backoff and jitter on transient failures (connection errors, timeouts, 5xx/421 SMTP). Permanent failures (5xx mailbox errors) are not retried. | Fake-adapter tests for transient vs permanent failure and the timeout. |
| NFR5.2 | When sending a code still fails, the API returns `UPSTREAM_UNAVAILABLE` (502) or `UPSTREAM_TIMEOUT` (504). The user and code records stay consistent: the code row is marked superseded so it can never be verified, and the user can resend after the cooldown (resolves functional design review R-04, the "orphan code" wording). | Test: email failure → 502 and the code is not verifiable; resend after 60 s works. |
| NFR5.3 | Server-side time budgets nest inside the frontend's: email 10 s × 3 attempts plus backoff stays under the 30 s frontend timeout. The worst case is capped at 25 s by stopping retries when the total elapsed time would exceed it (contract review R-06). | Test with a slow fake: the response returns by 25 s. |
| NFR5.4 | Database errors at request time return `INTERNAL_ERROR` (500), with the exception logged at ERROR with a request id. Transactions roll back, and no partial user or code state is left (one transaction per command). | Test with an injected database failure mid-transaction. |
| NFR5.5 | Start-up fails fast with a clear message when configuration is invalid, the database is unreachable, or migrations are not at head. `GET /health` reports `ok` only when the process is serving. A separate readiness check (`GET /health/ready`, public, no details) also checks the database. | Start-up tests; health endpoint tests. |
| NFR12.1 | The email adapter is selected by configuration (`EMAIL_BACKEND=smtp/fake`). SMTP host, port and credentials come from configuration. Locally the default is the mail catcher; tests use the recording fake. | Configuration tests (BR7.4–BR7.6). |
| NFR12.2 | Email templates (sign-up code, login code) are plain text plus simple HTML containing the code and its expiry time, with no tracking pixels or external images. | Snapshot test of the rendered email. |

**Graceful degradation:** the email provider is the only external dependency in this unit. When it is down, sign-up and login step 1 fail with a clear retryable message; nothing else is affected.

**Backup and recovery:** PostgreSQL backup is a hosting concern (deferred). Locally, the database runs in a Docker volume.
