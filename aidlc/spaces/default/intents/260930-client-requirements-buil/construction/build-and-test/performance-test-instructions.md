# Performance Test Instructions

- Auth/health latency p95 (U1/U2 NFR targets): `cd backend && uv run pytest tests/identity/test_perf_auth.py tests/health/test_perf_health.py tests/identity/test_perf_sessions.py tests/identity/test_perf_enumeration.py -m perf -q` (run by `verify.sh`).
- Session timing in the browser: reload stays signed in ≤ 1.5 s; two tabs refresh together ≤ 1 s (`e2e/session.spec.ts`).
- Analysis end-to-end within 10 minutes (NFR4) with the committed realistic-latency fake profile: `backend/tests/analysis/test_wiring_and_budget.py`. The real-vendor timed run (AC7.2.6) is an opt-in evaluation before handover.
- Bundle budget ≤ 200 KB gzipped per route: `cd frontend && node scripts/size-check.mjs` after `pnpm build`.
