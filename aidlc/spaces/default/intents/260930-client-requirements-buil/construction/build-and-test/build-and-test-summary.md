# Build and Test Summary

## Overall status
**Build: success. Tests: all passed.** Prerequisites and commands are in `build-instructions.md`; results in `test-results.md`.

## Test types
Unit + integration (backend pytest on real PostgreSQL; frontend Vitest/RTL), latency (p95), E2E journeys with accessibility (Playwright + axe, Chromium/WebKit/Firefox), security (Gitleaks, pip-audit, pnpm audit, deny-list, app independence), requirement-to-test map, bundle budget. Instruction files: `integration-test-instructions.md`, `performance-test-instructions.md`, `security-test-instructions.md`.

## Coverage per unit
Every unit runs inside the whole-app suites; whole-app line coverage is the enforced floor (backend 98.32%, frontend 96.9%; each ≥ 80%). Per-unit AC coverage: `cross-unit-traceability.md` (404 of 409 IDs covered, 5 N/A or Deferred with reasons, 0 uncovered).

## Target Verification Matrix
| Target ID | Source | Expected | Actual | Evidence | Owning Stage | Verdict |
|---|---|---|---|---|---|---|
| TC-COV-BE | Testing Contract (team.md Testing Posture) | ≥ 80% backend line coverage | 98.32% | verify.sh backend tests | build-and-test | Met |
| TC-COV-FE | Testing Contract | ≥ 80% frontend line coverage | 96.9% | verify.sh frontend tests | build-and-test | Met |
| TC-REQ-MAP | Testing Contract (requirement coverage) | every FR/AUTH/BR/FE ID mapped | 57/57 OK | `scripts/check-requirement-map.py` | build-and-test | Met |
| TC-SUITE | Testing Contract scope floor | existing suite green | 938 + 363 + 50 E2E passed, 0 failed | verify.sh | build-and-test | Met |
| NFR-PERF-AUTH | u1/u2 `nfr-requirements/performance-requirements.md` | auth p95 ≤ 500 ms; me ≤ 100; health ≤ 50; refresh/logout/resend ≤ 200 | all within (max 119.9 ms) | verify.sh latency step | build-and-test | Met |
| NFR-PERF-ENUM | u2 `nfr-requirements/security-requirements.md` | forgot-password timing spread < 50 ms | ≈ 2.8 ms p95 spread | `test_perf_enumeration.py` | build-and-test | Met |
| NFR-PERF-SESSION | u2 `nfr-requirements/performance-requirements.md` | reload signed in ≤ 1.5 s; two tabs ≤ 1 s | passed | `e2e/session.spec.ts` | build-and-test | Met |
| NFR-BUNDLE | u1 `nfr-design/performance-design.md` | ≤ 200 KB gzipped JS per route | max 197.1 KB (20 routes) | `size-check.mjs` | build-and-test | Met |
| NFR-A11Y | u1/u2 NFR + AC1.13.3 | no WCAG 2.1 AA violations on main screens | axe clean | `e2e/journey.spec.ts` + per-spec axe | build-and-test | Met |
| NFR-XBROWSER | AC1.13.2 | main journeys pass on 360 px + desktop in Chromium, WebKit, Firefox | passed | verify.sh E2E | build-and-test | Met |
| NFR-SEC-SECRETS | u1 `nfr-requirements/security-requirements.md` | no secrets in tree | no leaks | Gitleaks | build-and-test | Met |
| NFR-SEC-DEPS | u1 security requirements | no known vulnerable dependencies | none | pip-audit, pnpm audit | build-and-test | Met |
| NFR-SEC-AUTH | u1/u2 security requirements | no third-party auth; apps independent | OK | deny-list, app-independence | build-and-test | Met |
| NFR-CHECKPOINT | u2 infrastructure post-review R-01 | checkpoint journey ≤ 110 s | 47–53 s warm | `verify-skeleton.sh` | build-and-test | Met |
| NFR-ANALYSIS-TIME | NFR4 / AC7.2.5 | all narratives + 24 images within 10 min (realistic fake profile) | passed | `tests/analysis/test_wiring_and_budget.py` | build-and-test | Met |

## Readiness
- Build-ready: yes. Test-ready: yes.
- Deployment-ready: not applicable — no hosting is decided (NFR-010); no deployment stage is in this workflow.

## Known limitations / outstanding items
- Opt-in evaluations against real paid vendors are not part of the default run and remain for the client before handover: AC7.2.6 (timed real-vendor run), AC7.9.4 (real-model narratives), AC9.1.4 (image resemblance), AC10.1.7 / AC10.2.2 (chat grounding and medical decline; `RUN_CHAT_EVAL=1`).
- AC1.3.2: branch protection on `main` is a GitHub repository setting an admin applies after push (`docs/branch-protection.md`).
- Formulas, thresholds, label bands and prompts are first-pass `[Decided by delivery team]` values in configuration, pending client calibration (ASM-002, ASM-007, ASM-010, ASM-011).
- Timing-sensitive E2E: the two-tab refresh check (≤ 1 s) failed once in about ten checkpoint runs on this machine under load and passed on immediate re-run; worth watching in CI.
