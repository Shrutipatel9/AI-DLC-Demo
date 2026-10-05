<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-30T11:44:52Z — No rough mockups exist in this workflow, so screens were designed straight from the stories and the report design specification; the Home Overview is the specification dashboard (Protocol Summary).
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-30T11:44:52Z — Darkened four colours from the report specification (subheading, small accent text, muted text on grey, photo chip opacity) because the approximated values fail WCAG AA contrast; the specification itself marks them as approximations.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-30T11:44:52Z — One six-digit code field instead of six boxes, keeping paste and one-time-code autofill reliable at the cost of the look of the reference.
- 2026-09-30T11:44:52Z — Confirm dialog focus starts on Cancel so the safe choice is the default for destructive actions.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-09-30T11:44:52Z — Facial Age appears in the report specification dashboard but not in the client Home list; kept as working-spec content, to confirm with the client along with one-vs-several protocol phases.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
