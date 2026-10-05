## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-02T07:24:28Z
**Iteration:** 1

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | frontend/src/lib/auth/refresh-coordinator.ts > logout(); frontend/src/lib/auth/api.ts > postLogout() | logout() holds the exclusive auth-refresh lock for the whole /auth/logout call. postLogout uses apiRaw with the default 30 s client timeout, so a hung logout can block refreshes in every other tab for up to 30 s. The refresh path is bounded to 10 s per hold (NFD post-review R-08), but the logout hold is not. | Pass a timeoutMs of 10 s (or reuse REFRESH_TIMEOUT_MS) for postLogout so the lock hold has the same bound; the tab already signs out whatever the server says. | New |
| R-02 | Minor | backend/app/identity/routes.py > refresh handler parameter x_refresh_attempt (Header max_length=64) | sessions.py and the NFD pseudocode say a malformed attempt id counts as absent. A header longer than 64 characters instead fails FastAPI validation with 422 before the handler runs, so that response does not clear the cookie and does not follow the "every refresh refusal is 401 with cookie cleared" contract. No session state changes and the real client never sends such a value, so this is a contract-consistency gap only. | Drop max_length and let is_valid_attempt_id decide (the 22-character regex already rejects long values), or add a test pinning the intended 422. | New |
| R-03 | Minor | frontend/src/components/feedback/confirm-dialog.tsx > onKeyDown; confirm.ts > confirm() | The focus trap and Escape handling are attached to the dialog element only. If focus leaves a button (for example a click on the dialog body text moves focus to body), Escape and the Tab cycle stop working, and the page behind is not made inert (aria-modal only). confirm() throws synchronously for a generic label instead of returning a rejected promise. Deviation 3 (in-house dialog instead of AlertDialog) is justified by the bundle budget, but the trap is weaker than a library one. | Listen for keydown on document while the dialog is open (or keep focus inside on focusout), and optionally set inert on the app root. Make confirm() reject instead of throwing. Add an RTL test for Escape after a click on the body text. | New |
| R-04 | Minor | aidlc/spaces/default/intents/260930-client-requirements-buil/construction/u2-session-security/code-generation/code-summary.md > Deviations from the plan; frontend/src/lib/auth/refresh-coordinator.ts > claims array | The summary lists 12 deviations while the dispatch and plan refer to 11 decisions and deviations, so the ledger and the plan do not agree on a count. All 12 are individually justified. Separately, the coordinator claims array is only filtered by age, never pruned, so it grows by one entry per peer claim in a long-lived tab (negligible but unbounded). | Reconcile the count (state which item is plan-external), and drop claims older than CLAIM_CAP_MS when pushing a new one. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| source-manifest.json existence check (112 paths) | PASS: every path exists | Manifest matches the workspace. |
| traceability.json target check (62 file targets) | PASS: all resolve to existing files | Traceability targets are valid. |
| Code reading of sessions.py against NFD post-review R-02 | PASS | Parent then child lock order, recovery conditions (22-character base64url id, constant-time hash compare, child unused and at most 60 s old and unexpired), every branch commits before returning a Refused, route clears the cookie on every Refused, parent re-check after the child insert, deadlock retry once. |
| Code reading of repositories.revoke_sessions | PASS | Lock-then-update with token_id ordering and a separate UPDATE statement; used by logout (whole family, even from a rotated cookie), reset (all) and change (all but the verified cookie family). |
| Code reading of password_reset.py, shadow.py, delivery.py | PASS | Equal work before the reply on every branch, background task opens its own session, supersede by code id only, token consumed by a conditional update with a row-count check inside one transaction with the password change and revocation. |
| Code reading of login, change-password, csrf.py, middleware.py, settings.py, logging.py | PASS | Lockout checked only after a correct password; cookie secret verified before keeping the family; CORS outermost with GET, POST, OPTIONS and the extra headers; null and missing origins refused; Path must be /auth; SameSite none needs Secure; EMAIL_HASH_KEY at least 32 bytes; hide_parameters plus a formatter that drops the DB error message and DETAIL line. |
| Code reading of refresh-coordinator.ts and client.ts | PASS | Single flight per tab and across tabs, retry with the same attempt id after the lock is released, 10 s abort, 5 s or newer-expiresAt adoption, generation discard, logout takes the lock, claim fallback with 12 s cap, 401 handler matches NOT_AUTHENTICATED only, no Web Storage in non-test code. |
| Race tests (test_sessions.py) | PASS (read, not run) | Real PostgreSQL with two sessions in threads and a lock-waiter probe; not tautological. verify.sh reported green by the developer and was not re-run, as instructed. |
| CI workflow and verify.sh | PASS | Same gates in the same order, coverage floors enforced, no relaxed targets; the one-re-run latency retry is documented (D10). |

### Summary

The unit implements the security-critical paths faithfully to the final NFD pseudocode: ordered locking, strict reuse detection with attempt-id recovery, family-wide lock-then-update revocation, atomic single-use reset, equal-work non-revealing endpoints, outermost CORS plus origin-checked CSRF, and a coordinator whose races are covered by real-database and fake-lock tests. No Critical or Major findings were found; the four Minor items are a logout lock-hold bound, a 422-versus-401 edge on an oversized attempt header, a weaker custom dialog focus trap, and ledger and housekeeping nits. A developer could build from this unit without further architectural guidance.
