## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-01T13:14:00Z
**Iteration:** 1

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | aidlc/spaces/default/intents/260930-client-requirements-buil/construction/u2-session-security/infrastructure-design/cicd-pipeline.md > Verification command (checkpoint) | The time budget does not add up. U1 took 93 s against a limit of about 2 minutes, and the session spec is budgeted at 20 s, giving 113 s. That is already above the document's own 110 s split trigger, so the fallback fires by design. The spec has six scenarios at two viewports with axe, a two-tab refresh, a reset through Mailpit and password hashing on every sign-up, so 20 s is unrealistic. The split is also left as a later contingency, so the checkpoint can fail at code generation time. | Decide the checkpoint scope now. Run in verify-skeleton.sh only a short subset (reload stays signed in, cross-tab logout, reset) at one viewport, and keep the full two-viewport journey in CI and verify.sh. Alternatively record an explicit raised verifier limit. State the expected total in seconds. | New |
| R-02 | Major | aidlc/spaces/default/intents/260930-client-requirements-buil/construction/u2-session-security/infrastructure-design/cicd-pipeline.md > e2e row, and infrastructure-specification.md > New configuration | The per-IP limit for register, login, verify, resend, forgot, reset and change is AUTH_RATE_LIMIT_PER_MINUTE (20) in the security design, and every e2e call comes from 127.0.0.1. The skeleton spec plus the session spec make well over 20 of these calls within a minute, because each scenario needs its own sign-up and code verify. 429 flakes are likely in both verify-skeleton.sh and CI. The plan does not raise or reset the limit for the test environment, and ci-env.sh sets no such value. | Add a test-environment value for AUTH_RATE_LIMIT_PER_MINUTE and REFRESH_RATE_LIMIT_PER_MINUTE in ci-env.sh, or clear the limiter table between specs. List it in the configuration table. The default of 20 must stay unchanged for production. | New |
| R-03 | Minor | aidlc/spaces/default/intents/260930-client-requirements-buil/construction/u2-session-security/infrastructure-design/infrastructure-specification.md > New configuration table | The NFR design says the settings validator refuses SameSite=None without Secure, which implies a cookie SameSite setting. The table lists no such setting, only REFRESH_COOKIE_PATH. ci-env.sh shows only REFRESH_COOKIE_SECURE. The completeness claim cannot be confirmed. | Add the SameSite setting to the table with its default of Lax, or state that it is inherited from U1 and name it. Also record the AUTH_RATE_LIMIT_PER_MINUTE default as inherited. | New |
| R-04 | Minor | aidlc/spaces/default/intents/260930-client-requirements-buil/construction/u2-session-security/infrastructure-design/cicd-pipeline.md > Changes by job (backend perf step, e2e step) | The existing CI perf step names its files explicitly (test_perf_auth.py and test_perf_health.py), so the new tests/identity/test_perf_enumeration.py would not run. The e2e step runs only e2e/skeleton.spec.ts, so session.spec.ts would not run in CI. The document says what runs but not that ci.yml changes. | State that ci.yml edits add test_perf_enumeration.py to the perf step and e2e/session.spec.ts to the Playwright step, and that the failure artifact upload covers it. | New |
| R-05 | Minor | aidlc/spaces/default/intents/260930-client-requirements-buil/construction/u2-session-security/infrastructure-design/infrastructure-specification.md > New configuration (EMAIL_HASH_KEY) | The key is required with no default, but the plan does not say what backend/.env.example contains. A placeholder that looks real, or one under 32 bytes that the validator accepts, would weaken the secret rule. | State that .env.example carries an obvious placeholder the validator refuses. Name the validator check for the 32-byte minimum. Say that ci-env.sh keeps its keep-if-set behaviour for this key. | New |
| R-06 | Minor | aidlc/spaces/default/intents/260930-client-requirements-buil/construction/u2-session-security/infrastructure-design/traceability.json > upstream_ids | NFR9.9 and NFR2.17 were added by the requirements post-review note and are mentioned in cicd-pipeline.md, but they are not rows in the coverage list. NFR2.17 (CORS allow-list) has no listed target, although CSRF_ALLOWED_ORIGINS and its preflight tests exist. | Add NFR2.17 and NFR9.9 to upstream_ids and coverage with the targets already named in the documents. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| Manual feasibility check against ci.yml, ci-env.sh and verify-skeleton.sh | Four jobs and the checkpoint script exist as described. ci-env.sh generates and masks keys correctly. | The pipeline structure is sound. Time budget and test-environment rate limits are the gaps (R-01, R-02). |
| Configuration cross-check against the NFR design | Every named setting in the NFR design appears except a SameSite setting | Confirms R-03. |
| Secrets review | No repository secret. Throwaway per-run keys, masked, step-scoped. | Correct. See R-05 for the example file. |
| Contradiction check against the NFR post-review notes | No contradictions found. Reset journey, lock-then-update tests, CORS and timing tests are consistent. | OK. |

### Summary

U2 adds no new service and the plan is largely runnable and secure, with correct secret handling and no conflict with the NFR design. Two Major planning gaps remain. The checkpoint time budget is already over its own split threshold, and the e2e journeys will likely hit the per-IP auth rate limit. Both should be fixed before code generation, but neither makes the unit unbuildable, so the verdict is READY.
