# Observability Requirements — U1 Walking Skeleton

**Sources:** `requirements.md` NFR3 (no sensitive data in logs), NFR5 (errors surfaced, never swallowed), and the construction guardrails. Hosting and a monitoring stack are undecided, so the requirements here are **host-neutral**: structured logs on stdout and metrics endpoints any platform can collect. They are **[Decided by delivery team]**.

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR5.6 | **Structured JSON logs** on stdout. Fields: `timestamp` (ISO-8601 UTC), `level`, `logger`, `message`, `requestId`, `event`, and allow-listed context fields. Any field not on the allow-list is dropped by the formatter. | Formatter unit test. |
| NFR5.7 | Every request gets a `requestId`: taken from an incoming `X-Request-ID` if it is well-formed (UUID), otherwise generated. It is returned in the `X-Request-ID` response header and in error bodies. | Middleware test. |
| NFR5.8 | **Auth events** are logged at INFO with `event` names: `auth.signup.requested`, `auth.code.sent`, `auth.code.failed` (with attemptsLeft), `auth.code.locked`, `auth.verified`, `auth.login.failed`, `auth.login.code_sent`, `auth.rate_limited`. Each carries the user id (when known) and the masked email, never the code or password (NFR3.2). | Test captures logs for each flow and asserts the event names and absent secrets. |
| NFR5.9 | Errors: every unhandled exception is logged once at ERROR with stack trace and `requestId` (stack traces only in logs, never in responses). Vendor failures log the adapter name and error class at WARN on retry and ERROR on final failure. | Tests with forced failures. |
| NFR5.10 | **Metrics:** request count, error count and latency histogram per route (RED). Counters for `auth_codes_sent_total`, `auth_code_failures_total`, `auth_lockouts_total` and `rate_limited_total`. Exposed at `/metrics` in Prometheus text format, only when `METRICS_ENABLED=true`, and only from a configurable bind or IP allow-list. | Test: the metrics endpoint lists the named series; disabled by default. |
| NFR5.11 | Frontend: client-side errors caught by an error boundary are logged to the browser console with the `requestId` of the failing API call. No third-party error tracking yet (no host or vendor chosen). | Vitest test of the error boundary. |
| NFR5.12 | Log levels are configurable (`LOG_LEVEL`, default INFO). DEBUG never logs request or response bodies of `/auth/*`. | Configuration test. |

**SLIs to adopt when hosting exists (recorded, not implemented):**
- auth success rate (verified / code sent);
- error rate on `/auth/*` below 1% over 5 minutes;
- p95 latency per NFR9.1.

Alerts and dashboards belong to the Operation phase.
