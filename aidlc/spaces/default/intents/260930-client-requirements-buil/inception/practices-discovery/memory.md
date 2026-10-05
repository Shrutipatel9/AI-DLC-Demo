<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-30T09:34:02Z — Read the 80% coverage floor as whole-app line coverage enforced by the test tools at every merge, and applied the lint-enforced layering to the backend token and one-time-code services as well as the frontend, since the client layering covers both.
- 2026-09-30T09:19:34Z — The quality engineer read the organisation rule on running CI before merge as not replaceable by a local run, so the interview offered local-only checks as a recorded gap rather than an equal option; the human chose a GitHub Actions workflow in the first piece of work.
- 2026-09-30T09:01:29Z — Greenfield practices seeded from org.md defaults plus the stack in client_requirements.md; org defaults are treated as suggestions until the interview confirms them, and tool choices (Ruff, pytest, Vitest, Playwright) stay tagged as suggestions.
- 2026-09-30T09:01:29Z — Client items labelled [Decided by delivery team] (e.g. httpOnly refresh cookie, OTP limits) were treated as hard constraints because the client explicitly delegated and recorded them as decided; pure ASM-* recommendations stay as candidate rules.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-30T09:34:02Z — The team chose to build a thin end-to-end slice first (sign-up, emailed code, login, who-am-I) although this workflow type defaults to no skeleton; the team practice now records the skeleton as always on for greenfield work here.
- 2026-09-30T09:01:29Z — The org default of deploying on merge to staging is not applied in this workflow; hosting is undecided (NFR-010, CON-007) and the operation stages are skipped, so it is kept only as a future target.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-30T09:19:34Z — Chose tests-first only for the riskiest logic (token and one-time-code services, frontend token refresh, same-person photo check) and tests-after elsewhere; this keeps the organisation default while guarding the security-critical paths.
- 2026-09-30T09:19:34Z — Kept design-level choices (sync vs async database access, API error format, JSON casing, route prefix, Next.js rendering under in-memory tokens) out of the practices interview and deferred them to the design stages so practices stay about how the team works.
- 2026-09-30T09:01:29Z — The classic default requires CI before merge, but the CI stage is skipped and no CI exists; the options are a minimal GitHub Actions workflow built during construction or a recorded local lint and test run at each piece-of-work gate, and this goes to the interview.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-09-30T09:19:34Z — Whether medical, medication and allergy answers are sent to OpenAI at all (FR-008 vs FR-008(f)), and which user jurisdictions apply for biometric and health data, need a client or requirements decision.
- 2026-09-30T09:19:34Z — Two browser tabs refreshing at once could trip refresh-token reuse detection (AUTH-012) and log the user out, conflicting with FE-006; needs a design decision.
- 2026-09-30T09:01:29Z — The repository was initialised on an unborn master branch while the trunk rules assume main; this has to be settled before the first construction worktree is created.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
