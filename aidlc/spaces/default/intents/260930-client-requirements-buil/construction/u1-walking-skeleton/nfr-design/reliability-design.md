# Reliability Design — U1 Walking Skeleton

**Sources:** `nfr-requirements/reliability-requirements.md` (NFR5.1–NFR5.5, NFR5.13, NFR12.x) and NFR design answer Q1 (no circuit breaker yet).

## 1. Failure-mode table

| Dependency | Failure | Behaviour | Blast radius | Recovery |
|---|---|---|---|---|
| Email provider | Timeout, connection error, 4xx/5xx | Retry within the 25 s budget; then 502/504 and the code is superseded | One sign-up or login attempt | User retries after the 60 s cooldown; automatic when the provider recovers |
| PostgreSQL | Unreachable at start-up | The process exits non-zero with a clear message | Whole API (fail fast) | Start the database, restart the process |
| PostgreSQL | Error mid-request | Rollback; 500 `INTERNAL_ERROR` logged with request id | One request | Automatic on the next request |
| PostgreSQL | Pool exhausted | Waits up to `DB_POOL_TIMEOUT` (5 s), then 500 | Concurrent requests | Load drops, or pool tuning (NFR11.5) |
| Frontend → API | Network error or 30 s timeout | A friendly retry message on the form; no partial state | One browser tab | User retries |

## 2. Email sending (NFR5.1, NFR5.3, NFR5.13)

The design follows a **commit → send → compensate** sequence. The email call never holds a database connection or a row lock.

```mermaid
sequenceDiagram
  participant R as Route
  participant S as CodeIssuer
  participant DB as PostgreSQL
  participant M as EmailSender
  R->>S: issue(user, purpose)
  S->>DB: tx1: supersede old code, insert new code, update counters, COMMIT
  S->>M: send(email, code) with budget 25 s
  alt sent
    S-->>R: ok
  else final failure
    S->>DB: tx2: mark code superseded, COMMIT
    S-->>R: UpstreamUnavailable / UpstreamTimeout
  end
```
Text fallback: the code issuer commits the new code in transaction 1 and releases the connection, then sends the email with a 25-second budget. On final failure, a short transaction 2 marks the code superseded, and the route returns 502 or 504.

**Retry policy (`RetryPolicy`, shared by later vendor adapters):**
- Maximum attempts: 3 (1 + 2 retries).
- Delay = `min(4 s, 0.5 s × 2^attempt) + random(0, 250 ms)`.
- Per-attempt timeout = `min(10 s, remaining_budget)`. No attempt starts with less than 2 s remaining.
- Retryable: connection errors, timeouts, SMTP 421/450/451/452 and 5xx from HTTP providers. Not retryable: SMTP 550/553 and other permanent rejections.
- The total budget is 25 s, measured from the first attempt (NFR5.3).

**Thread pool:** sync endpoints run in AnyIO's thread pool. The design sets its capacity explicitly to 40 at start-up (`anyio.to_thread.current_default_thread_limiter().total_tokens = 40`). Up to 40 slow sends can wait without starving the database pool (5 + 5).

**No circuit breaker (answer Q1):** at launch volume, a breaker adds state without real benefit. Every request already fails within its budget. Revisit when traffic or a second vendor call path exists. The `EmailSender` port makes adding one a single-adapter change.

## 3. Transactions (NFR5.4)
- One `Session` per request from a `get_session` dependency, with `expire_on_commit=False`.
- Services take the session and commit explicitly. The dependency rolls back on any exception and always closes the session.
- Multi-step commands (verify, issue code) are one transaction each, except the email compensation (tx2), which is deliberately separate.
- No transaction spans an outside call.

## 4. Health and start-up (NFR5.5)

| Check | Path | Does | Used by |
|---|---|---|---|
| Liveness | `GET /health` | Returns `{"status":"ok"}`, no I/O | Process supervisors, NFR9.3 |
| Readiness | `GET /health/ready` | `SELECT 1` plus a check that Alembic is at head; 200 or 503 with no details | Compose healthcheck, `make verify`, future load balancer |
| Start-up | App lifespan | Validates settings, connects to the database, and checks that migrations are at head; exits with code 1 on failure | Fail fast |

Graceful shutdown: Uvicorn drains in-flight requests on SIGTERM (a 10 s timeout, set in the run command), and the lifespan disposes the engine.

## 5. Email templates (NFR12.1, NFR12.2)
Templates are a plain-text and an HTML Jinja2 file per purpose (`signup_code`, `login_code`). They contain the code, the expiry time ("valid for 10 minutes") and a "didn't ask for this?" line, with no images or links. The adapter is chosen by `EMAIL_BACKEND` (`smtp` or `fake`). Development uses SMTP to Mailpit on port 1025; tests use the recording fake.

## 6. Backup and recovery
Deferred until hosting is chosen. Locally, the `pgdata` Docker volume persists across restarts, and `make db-reset` recreates it.
