<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-30T10:45:11Z — Read the client "seven measured features" as the seven front-mesh features (Eyebrows, Eyes, Nose, Cheeks, Jaw, Lips, Chin) with Ears measured separately from the 3/4 photos; flagged for client confirmation.
- 2026-09-30T10:45:11Z — The questionnaire, capture, identity and report documents in the space knowledge folder were adopted as working specifications on the human decision (Q7), while staying labelled as not client-confirmed.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-30T10:45:11Z — Corrected the requirements-stage hub case: when front matches both others but they differ, one non-front photo is now flagged instead of none, following BR-005 rule 2 and the identity specification; the requirements text still says none and should be aligned in design.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-30T10:45:11Z — Split large stories and added missing enablers (storage, landmark service, pipeline, routing, auth store), taking the count to 80 against the 50-70 estimate so each story stays 1-3 days (Q9).
- 2026-09-30T10:45:11Z — AI-quality checks moved to an opt-in evaluation suite with deterministic fake-based companions, keeping the no-paid-calls rule for default tests.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-09-30T10:45:11Z — Hub-case tie-break, symmetry label bands, distress trigger levels, dimorphism formulas, priority-feature rule and the two-tab refresh mechanism are left for functional and domain design.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
