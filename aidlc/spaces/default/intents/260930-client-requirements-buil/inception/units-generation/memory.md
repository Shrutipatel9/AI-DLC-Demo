<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-30T12:34:25Z — Derived the unit dependency graph from the stories own Deps lines and checked it by script, so the unit order cannot contradict the story order.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-30T12:34:25Z — Treated the US6.2 dependency on US1.12 as a mislabelled need for a Stripe adapter and built that adapter inside the payments unit, rather than making payments wait for the analysis unit.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-30T12:34:25Z — Put journey routing and the landing page in the last unit because routing needs every stateful module; earlier units use temporary links, accepting a little throwaway routing code.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-09-30T12:34:25Z — Story dependencies make the build almost a straight chain (only the chat and settings units are independent); delivery planning should decide whether any early parallel work is worth splitting stories further.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
