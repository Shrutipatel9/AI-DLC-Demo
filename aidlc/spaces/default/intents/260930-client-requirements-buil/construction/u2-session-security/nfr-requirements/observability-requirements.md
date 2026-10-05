# Observability Requirements — U2 Session Security

**Sources:** U1 observability (JSON logs, request id, opt-in metrics), NFR5, and answer Q2 (structured logs only). Hosting is undecided, so this stays host-neutral.

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR5.9 | The security events in NFR5.12 (security requirements §3) use the U1 allow-listed fields plus `familyId`, `reason`, `count` and `purpose`. They never include secrets, reset tokens, attempt ids or full emails. | Formatter test with the new fields; canary test. |
| NFR5.10 | **New metrics** (on the opt-in `/metrics` endpoint): `auth_refresh_total{outcome}` with outcomes `ok`, `expired`, `invalid`, `revoked`, `reuse_detected`, `recovered` and `csrf_refused`; `auth_sessions_revoked_total{reason}`; `auth_password_resets_total{step}`; `auth_password_changes_total{outcome}`. Labels never carry user or family ids. | Metrics test lists the series. |
| NFR5.11 | **Frontend:** session outcomes are logged to the browser console in development only: refresh failure class, sign-out reason, and lock fallback mode. Never tokens. | Vitest test of the logger guard. |

**SLIs to adopt when hosting exists (recorded, not built):**
- Refresh success rate: `ok + recovered` / all, excluding `csrf_refused`.
- Reuse-detection rate: an alert threshold is proposed at more than 5 per hour, which suggests token theft or a client bug.
- Password-reset completion: reset / reset_requested.
