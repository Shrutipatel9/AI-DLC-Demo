# Monitoring Design — U2 Session Security

**Sources:** U2 observability design and its post-review note (R-07), and U1 monitoring design. No hosted monitoring exists in this workflow. These are host-neutral targets for the Operation phase.

## Metrics & KPIs

| Metric | Source | Threshold | Why it matters |
|---|---|---|---|
| `auth_refresh_total{outcome}`: share of `ok` and `recovered` | `/metrics` | ≥ 99% excluding `csrf_refused` | Users stay signed in |
| `auth_refresh_total{outcome="reuse_detected"}` | `/metrics` | > 5 per hour | Possible token theft or a client coordination bug |
| `auth_refresh_total{outcome="recovered"}` | `/metrics` | Unusual rise | Network trouble between clients and the API |
| `auth_sessions_revoked_total{reason}` | `/metrics` | Spike in `password_reset` | Possible account-takeover wave |
| `auth_password_resets_total{step}` completion (`completed` / `requested`) | `/metrics` | < 50% daily | The reset journey is broken or emails are failing |
| `http_request_duration_seconds` p95 for `/auth/refresh` | `/metrics` | ≤ 0.2 s | NFR9.1 |

## Alerts

These are recorded for the Operation phase; nothing routes yet.

| Alert | Condition | Severity | Routes to |
|---|---|---|---|
| Reuse detections high | `reuse_detected` > 5 in 1 hour | Ticket | Team (security review) |
| Refresh failures | Share of `ok` and `recovered` < 97% for 15 minutes | Page (P2) | On-call |
| CSRF refusals spike | `csrf_refused` > 50 in 10 minutes | Ticket | Team (possible attack or a misconfigured origin) |
| Reset emails failing | `vendor.failed` from the email adapter on reset > 5 in 10 minutes | Page (P2) | On-call |

## SLIs / SLOs

| SLI | SLO target | Measurement window |
|---|---|---|
| Refresh success (`ok` + `recovered`) / all, excluding `csrf_refused` | 99.5% | 30-day rolling |
| Refresh latency under 200 ms | 95% | 30-day rolling |

## Logs & Tracing
- **Security events** (observability design catalogue, as amended by post-review R-07) are JSON on stdout. Proposed retention once hosted: WARN 90 days, INFO 30 days.
- **No identifiers in metric labels.** `familyId` appears only in logs.
- **No tracing** (U1 decision). The request id still correlates every step.
- **Dashboard (future):** add a "Sessions" panel to the U1 "Sign-in health" board covering refresh outcomes, revocations by reason and the reset funnel.
