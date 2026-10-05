# Observability Design — U1 Walking Skeleton

**Sources:** `nfr-requirements/observability-requirements.md` (NFR5.6–NFR5.12) and NFR design answer Q2 (request id only; OpenTelemetry deferred).

## 1. Correlation
- **Backend:** a `RequestIdMiddleware` (first in the stack) puts the id in a `contextvars.ContextVar`. A logging filter copies it onto every record, and the exception handler copies it into error bodies (NFR5.7).
- **Frontend:** `apiClient` reads `X-Request-ID` from each response and attaches it to thrown `ApiError`s, so the error boundary can log it (NFR5.11).
- **Tracing (answer Q2):** no distributed tracing in U1. The request id is the one correlation key. OpenTelemetry is added when the worker (U6) or hosting arrives; the middleware position is where its span will start.

## 2. Structured logging (NFR5.6, NFR5.12)

```json
{"timestamp":"2026-10-01T10:00:00.123Z","level":"INFO","logger":"identity.verify","message":"code verified","requestId":"7f9c…","event":"auth.verified","userId":"0b3e…","email":"m•••@example.com"}
```
- The formatter is a small `JsonFormatter`, with no third-party logging library. It emits the allow-listed keys `timestamp, level, logger, message, requestId, event, userId, email, route, status, durationMs, attemptsLeft, adapter, errorClass` and drops all other keys.
- **Access log:** one INFO line per request from middleware: `event=http.request`, `route` (the template, e.g. `/auth/verify`, never a raw path with ids), `status`, `durationMs`. Uvicorn's own access log is disabled to avoid duplicates.
- `LOG_LEVEL` comes from settings. Even at DEBUG, no bodies, headers or cookies of `/auth/*` are logged.

## 3. Event catalogue (NFR5.8, NFR5.9)

| Event | Level | Fields |
|---|---|---|
| `auth.signup.requested` | INFO | email (masked) |
| `auth.code.sent` | INFO | userId, purpose |
| `auth.code.failed` | INFO | userId, purpose, attemptsLeft |
| `auth.code.locked` | WARN | userId, purpose |
| `auth.verified` | INFO | userId, purpose |
| `auth.login.failed` | INFO | email (masked) |
| `auth.login.code_sent` | INFO | userId |
| `auth.rate_limited` | WARN | route |
| `auth.email_cap_reached` | WARN | — |
| `vendor.retry` | WARN | adapter, errorClass, attempt |
| `vendor.failed` | ERROR | adapter, errorClass |
| `http.unhandled` | ERROR | exception with stack trace (logs only) |

## 4. Metrics (NFR5.10)
- `prometheus-client` with a dedicated `CollectorRegistry`.
- `/metrics` is mounted only when `METRICS_ENABLED=true`. Requests are allowed only from `METRICS_ALLOW_CIDRS` (default `127.0.0.1/32`); others get 403. It is exempt from token auth (see security design §1).
- Series:
  - `http_requests_total{route,method,status}`;
  - `http_request_duration_seconds{route,method}` (histogram buckets 5 ms–5 s);
  - `auth_codes_sent_total{purpose}`;
  - `auth_code_failures_total{purpose}`;
  - `auth_lockouts_total{purpose}`;
  - `rate_limited_total{route}`;
  - `email_send_failures_total{reason}`.
- Labels never contain user ids or emails.

## 5. SLIs, alerts and dashboards
Recorded for the Operation phase, not built now (no hosting):
- **SLI auth availability:** non-5xx responses / all on `/auth/*`. Proposed SLO 99.5% over 30 days.
- **SLI auth latency:** share of `/auth/*` requests under 500 ms. Proposed SLO 95% over 30 days (NFR9.1).
- **SLI code delivery:** `auth_codes_sent_total` / (sent + `email_send_failures_total`).
- **Proposed alerts:**
  - 5xx rate on `/auth/*` over 2% for 10 minutes (below the SLO breach);
  - code-delivery failure rate over 10% for 10 minutes;
  - any `auth.email_cap_reached`.
- **Dashboard (proposed):** RED panels per route, code funnel (sent → verified), lockouts and rate-limited counts.
