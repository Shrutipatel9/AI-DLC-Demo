# Scalability Requirements — U2 Session Security

**Sources:** `requirements.md` NFR11 (hosting neutrality), U1 scalability requirements (stateless processes, PostgreSQL-held state). No client growth figures exist. The requirements below are **[Decided by delivery team]**.

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR11.1 | All U2 session state lives in PostgreSQL: refresh families, reset tokens, attempt and shadow counters, and attempt ids. Any API instance can serve any refresh, logout, reset or change. | Test: two app instances against one database, alternating refreshes on one family. |
| NFR11.2 | Cross-tab coordination is purely client-side (Web Locks and BroadcastChannel) and adds no server state or sticky sessions. | Design review; no server component. |
| NFR11.3 | **Growth:** each refresh adds one `refresh_sessions` row, so at most about 96 rows per active user per day at one refresh per 15 minutes. Expired, rotated and revoked rows older than 30 days, used or expired reset tokens older than 30 days, and shadow counters idle for more than 1 day are removed by a maintenance command `auth-cleanup` (idempotent, runnable any time). | Test: the command deletes only eligible rows; a second run deletes nothing. |
| NFR11.4 | **Indexes:** `refresh_sessions(family_id)` for family revoke; `refresh_sessions(user_id) WHERE revoked_at IS NULL AND rotated_at IS NULL` for the revocations on reset and change; `password_reset_tokens(token_hash)` unique; `email_attempt_counters(email_hash, purpose)` primary key. | Migration review; `EXPLAIN` checks in tests for family revoke and user revoke. |
