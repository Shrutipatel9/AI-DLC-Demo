# Scalability Requirements — U1 Walking Skeleton

**Sources:** `requirements.md` NFR11 (hosting neutrality); `unit-of-work.md` deployment model (FastAPI modular monolith, web process + worker; Next.js app). No growth projections exist from the client. The requirements below keep the slice **horizontally scalable** without picking a host. They are **[Decided by delivery team]**.

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR11.1 | The backend web process is stateless. All session state lives in PostgreSQL (refresh sessions, codes, counters), so any number of web processes can serve any request. | Code review + test: two app instances against one database both validate the same token and verify the same code. |
| NFR11.2 | Per-IP throttling (NFR2.9) uses a store that works across processes. In U1 this is a PostgreSQL-backed sliding window (no new infrastructure), behind an interface so a shared cache can replace it later. | Interface test with the in-memory and PostgreSQL implementations. |
| NFR11.3 | Uniqueness and limits are enforced by the database (unique normalised email; row lock on the attempt counter), not process memory. | Concurrency tests (NFR2.10). |
| NFR11.4 | Configuration only (environment variables) decides database URL, origins, cookie domain and pool size. No host-specific code (BR8.5). | Configuration test; dependency review. |
| NFR11.5 | Expected volume for planning: up to 100 sign-ups per hour and 50 concurrent signed-in users at launch **[Assumption — no client figure]**. The default pool (5 + 5) and one web process are sized for this. Revisit when hosting and traffic are known. | Recorded assumption; reviewed in Operation (out of this workflow). |

**Data growth:** users and refresh sessions grow with sign-ups. Expired and revoked refresh sessions, and consumed or expired codes older than 30 days, are deletable by a maintenance command (built in U2, which owns session lifecycle). No retention policy is defined by the client (§2.2).
