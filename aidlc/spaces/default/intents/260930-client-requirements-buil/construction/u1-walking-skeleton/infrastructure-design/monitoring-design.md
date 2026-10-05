# Monitoring Design — U1 Walking Skeleton

**Sources:** `nfr-design/observability-design.md` (NFR5.6–NFR5.12) and team practice `## Deployment` (no host).

There is no hosted monitoring platform in this workflow. Monitoring for U1 is what the code emits, which any platform can collect later: JSON logs on stdout and an opt-in Prometheus endpoint. The tables below fix the names and thresholds now, so the Operation phase only has to wire them up.

## Metrics & KPIs

| Metric | Source | Threshold | Why it matters |
|---|---|---|---|
| `http_request_duration_seconds` p95, `/auth/*` | `/metrics` histogram | ≤ 0.5 s (≤ 0.1 s for `/auth/me`) | Sign-in latency targets (NFR9.1, NFR9.2) |
| `http_requests_total` 5xx share, `/auth/*` | `/metrics` counter | < 1% over 5 minutes | Sign-in availability |
| `auth_codes_sent_total` vs `email_send_failures_total` | `/metrics` counters | Failure share < 5% | Users cannot sign in without the email |
| `auth_lockouts_total` | `/metrics` counter | Sudden rise over 10 per hour | Possible guessing attack |
| `rate_limited_total` | `/metrics` counter | Sustained over 50 per hour | Abuse, or a limit set too low |
| Code funnel: `auth.verified` / `auth.code.sent` | Log events | Below 60% daily | Users get stuck at the code step (UX or delivery problem) |

## Alerts

These are recorded for the Operation phase. None route anywhere in this workflow, because there is no host or on-call.

| Alert | Condition | Severity | Routes to |
|---|---|---|---|
| Auth 5xx high | 5xx share on `/auth/*` over 2% for 10 minutes | Page (P2) | On-call engineer, once hosting exists |
| Auth latency high | p95 on `/auth/*` over 0.5 s for 15 minutes | Ticket | Team backlog |
| Code delivery failing | Email failure share over 10% for 10 minutes | Page (P2) | On-call engineer |
| Email cap reached | Any `auth.email_cap_reached` log | Ticket | Team backlog (check for abuse, or raise the cap) |
| Lockout spike | `auth_lockouts_total` rises by more than 20 in 1 hour | Ticket | Team backlog (security review) |
| API not ready | `/health/ready` non-200 for 2 minutes | Page (P1) | On-call engineer |

## SLIs / SLOs

| SLI | SLO target | Measurement window |
|---|---|---|
| Auth availability: non-5xx responses / all responses on `/auth/*` | 99.5% | 30-day rolling |
| Auth latency: share of `/auth/*` requests under 500 ms | 95% | 30-day rolling |
| Code delivery: codes sent / (sent + send failures) | 99% | 30-day rolling |

The alert thresholds above are set below the SLO breach points, so there is time to act before an SLO is missed (operation phase guardrail).

## Logs & Tracing

| Aspect | Design |
|---|---|
| Log output | JSON lines on stdout (API) and the console (web). Locally, the developer's terminal; in CI, job logs, plus the API log uploaded as an artifact when e2e fails |
| Log fields | The allow-list in observability design §2; masked emails; never secrets or bodies |
| Aggregation (future) | Any collector that reads container stdout (for example CloudWatch Logs, Loki or Datadog), chosen with the host |
| Retention (future) | ERROR and WARN 90 days, INFO 30 days, DEBUG not shipped |
| Correlation | `X-Request-ID` on every response and log line; the frontend logs it with failed calls |
| Tracing | None in U1 (NFR design answer Q2). OpenTelemetry is added with the worker (U6) or the host, starting at the request-id middleware |
| Metrics scraping | `/metrics` is off by default. Locally, `METRICS_ENABLED=true` plus `curl localhost:8000/metrics` lets a developer check the series; no Prometheus server runs in U1 |

**Dashboard specification (future):** one "Sign-in health" board with four panels:
- requests and errors per auth route;
- p95 latency per route against its target line;
- the code funnel (sent → verified) with lockouts and rate-limited counts;
- email send failures by reason.
