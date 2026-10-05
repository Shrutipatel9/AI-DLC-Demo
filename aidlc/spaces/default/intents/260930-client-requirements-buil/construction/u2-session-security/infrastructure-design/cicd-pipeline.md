# CI/CD Pipeline — U2 Session Security

**Sources:**
- U1 `cicd-pipeline.md` (all four jobs remain);
- U2 NFR design, read with its post-review note;
- the approved skeleton verification command `bash scripts/verify-skeleton.sh`.

U2 changes only steps inside the existing jobs. It adds no new job, and there is still no deployment.

## Changes by job

| Job | Change | Requirement |
|---|---|---|
| `backend` | New tests run inside the existing pytest step: sessions, reset, change, CSRF/CORS preflight, concurrency races and cleanup. The `perf` step adds the U2 endpoint latencies and the anti-enumeration timing test (200 samples per branch). `EMAIL_HASH_KEY` is added to the step-scoped throwaway keys from `scripts/ci-env.sh` | NFR2.x, NFR9.1–NFR9.5, NFR design post-review R-03 |
| `frontend` | New Vitest suites: `refreshCoordinator` (test-first), store, toast and dialog accessibility, and the new forms. The bundle size check stays at 200 KB | NFR5.x, NFR8.1, NFR9.8, NFR9.9 |
| `e2e` | The migration round-trip now includes `0002`. A new Playwright spec `e2e/session.spec.ts` runs after `skeleton.spec.ts`, at both viewports with axe, and covers:<br>- reload stays signed in<br>- two tabs refreshing together<br>- logout in one tab signs out the other<br>- forgot password → code from Mailpit → reset → login<br>- change password keeps this tab<br>- the logout dialog and toast accessibility | NFR8.3, NFR9.6, NFR9.7, NFR9.9 |
| `security` | Unchanged (Gitleaks, audits, deny-list, app independence) | — |

## Verification command (checkpoint)
`scripts/verify-skeleton.sh` is extended to run `e2e/session.spec.ts` after `skeleton.spec.ts`. The approved command text, `bash scripts/verify-skeleton.sh`, does not change, so no new approval is needed.

The whole command must still finish within the verifier's limit of about 2 minutes. The U1 run took 93 s, and the session spec is budgeted at 20 s or less. If the total goes over 110 s, the spec is split so the checkpoint runs the cross-tab and reset scenarios, and the full journey runs in CI and in `verify.sh`.

## Secrets
There is still no repository secret. `EMAIL_HASH_KEY` is generated per run and masked like the other keys (U1 D8).

## Rollback
Unchanged: revert the squash commit through a pull request. `0002` has a tested downgrade.
