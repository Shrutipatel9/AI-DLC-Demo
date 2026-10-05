# Scalability Design — U2 Session Security

**Sources:** `nfr-requirements/scalability-requirements.md` (NFR11.1–NFR11.4) and the U1 scalability design.

| Concern | Design | Requirement |
|---|---|---|
| Stateless API | Refresh families, reset tokens, attempt and shadow counters, and attempt hashes all live in PostgreSQL. Any instance serves any request; no sticky sessions | NFR11.1 |
| Client-only coordination | Web Locks and BroadcastChannel stay inside one browser. The server is unaware of tabs | NFR11.2 |
| Row growth | About one row per refresh per user. Cleanup, which runs as a command (reliability design §2), keeps table size bounded at about 30 days of history | NFR11.3 |
| Index plan | See performance design §2. Family revoke and user revoke use index scans; `EXPLAIN` checks run in the integration tests | NFR11.4 |
| Lock contention | Row locks are per session, so contention happens only between tabs of one user, and the client lock avoids even that. No table-level locks | NFR2.4 |
