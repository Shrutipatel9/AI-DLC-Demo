# Observability Design — U2 Session Security

**Sources:** `nfr-requirements/observability-requirements.md` (NFR5.9–NFR5.11), `security-requirements.md` NFR5.12 (security events, logs only), U1 observability design.

## Security event catalogue (NFR5.12, NFR5.9)

| Event | Level | Fields |
|---|---|---|
| `auth.session.refreshed` | DEBUG | userId, familyId |
| `auth.session.recovered` | INFO | userId, familyId |
| `auth.session.reuse_detected` | WARN | userId, familyId, count (sessions revoked) |
| `auth.session.refused` | INFO | reason (EXPIRED, INVALID or REVOKED) |
| `auth.csrf.refused` | WARN | route |
| `auth.logout` | INFO | userId, familyId, count |
| `auth.password.reset_requested` | INFO | email (masked), sent (true/false) — kept in logs only, never in the response |
| `auth.password.reset` | INFO | userId, count (sessions revoked) |
| `auth.password.changed` | INFO | userId, count (other sessions revoked) |
| `auth.code.locked` | WARN | userId or emailHashPrefix (first 8 hex characters), purpose |

The allow-list additions are `familyId`, `reason`, `count`, `sent`, `outcome` and `emailHashPrefix`. Values are never secrets.

## Metrics (NFR5.10)
- `auth_refresh_total{outcome}`, where `outcome` is one of `ok`, `recovered`, `expired`, `invalid`, `revoked`, `reuse_detected` or `csrf_refused`.
- `auth_sessions_revoked_total{reason}`.
- `auth_password_resets_total{step}`, where `step` is `requested`, `code_verified` or `completed`.
- `auth_password_changes_total{outcome}`.
- These are registered on the U1 opt-in registry. Labels never carry identifiers.

## Frontend (NFR5.11)
- A `sessionLog` helper writes to the console only when `process.env.NODE_ENV === "development"`.
- It records the refresh failure class, the sign-out reason and the lock mode (`locks`, `broadcast` or `none`).
- It never writes tokens or ids. A Vitest test asserts the production build is silent.

## Recorded SLIs (for the Operation phase)
- Refresh success rate.
- Reuse-detection rate, with a proposed alert above 5 per hour.
- Reset completion rate.
