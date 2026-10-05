**Collaborator:** aidlc-quality-agent

## Contribution

Quality-engineering review of `stories.md` and `personas.md` (Round 1). My test for every acceptance criterion: could a developer write a failing automated test from it today, with a clear pass/fail result, using the fakes the team has agreed to (`NFR-008`, `NFR-013`, team practices "Paid services are faked")? Anything not stated by the client is labelled **[Recommendation]** or **[Assumption]**, as the project mandates. Where I found a conflict between sources, I state it and leave the decision to the human or client.

Overall, the draft is strong. Most ACs are concrete Given/When/Then checks, and the engine-plus-blocked-content split (Q6) keeps the placeholder work testable. The gaps cluster in four places: (1) the three test-first modules, where boundaries and counter behaviour are not yet precise enough to write failing tests from; (2) the identity vote, where one outcome is never exercised and one case conflicts between sources; (3) criteria that depend on real AI output; (4) NFRs with no story coverage.

---

### 1. Test-first modules: missing precision (team practices, Testing Posture)

#### 1a. Backend OTP service (`AUTH-011`, FR2.4): US3.2, US3.3, US3.9

For each rule, say which side of the boundary passes, and use an injectable clock so tests never sleep. Proposed replacement or added ACs:

- **AC3.2.1 / AC3.2.2 (boundary).** Given a code issued at T, when the correct code is entered at T+9:59, then it is accepted; when it is entered at T+10:00, then it is refused as expired. [Recommendation: the code is valid while `now < issued_at + 10 min`, with the boundary value refused.]
- **New AC3.2.4 (single use).** Given a code that has already been used successfully, when it is entered again, then it is refused. [Recommendation, derived from FR2.3 "verify against … expiry and attempt limits"]
- **New AC3.2.5 (purpose binding).** Given a code issued for sign-up, when it is submitted to the login-verify or password-reset-verify step, then it is refused. [Recommendation]
- **AC3.3.1 (boundary).** Given a code sent at T, a resend at T+59s is refused and the response reports the remaining wait of 1 s; a resend at T+60s succeeds.
- **New AC3.3.4 (resend invalidates).** Given a resend succeeded, when the *previous* code is entered, then it is refused. **[Open: the client does not say this. It must be decided before test-first work, because it changes the data model.]**
- **AC3.3.2 (counter semantics).** The draft does not define these rules, and they are the point of a test-first module:
  - Is the failure counter kept per account and purpose, or per issued code? If it is per code, a resend resets it and the lockout can be bypassed. **[Recommendation: per account + purpose, not reset by resend.]**
  - Is resend allowed during lockout? **[Recommendation: no; the refusal reports the lockout end time.]**
  - Does a successful verification reset the counter? **[Recommendation: yes.]**
  - Boundary: 5th wrong code → the lockout starts at time L. At L+14:59, even a correct code is refused. At L+15:00, a newly requested correct code is accepted (replaces the vague "after the lockout has passed" in AC3.3.3).
- **AC3.9 (reset code).** Add: Given 5 wrong reset codes, then the reset flow locks for 15 minutes (FR2.12 "same rules as FR2.4"). This case has no AC today.
- **Status codes.** Lockout and cooldown status codes are deferred to Contract Design (requirements, Open Questions). The ACs can still be test-first if each refusal is asserted on a machine-readable error `code` field whose names Contract Design fixes. I suggest adding one line to the story conventions: "refused" means an error response in the shared format (US1.8) with a named `code`.

#### 1b. Backend JWT and refresh service (`AUTH-010`, `AUTH-012`, `AUTH-013`, `AUTH-015`, FR2.5–FR2.12)

Missing backend ACs. Today, only frontend ACs mention expiry.

- **New AC3.6.7 (access expiry, backend).** Given an access token issued at T, then a protected endpoint accepts it at T+14:59 and returns 401 at T+15:00.
- **New AC3.6.8 (refresh expiry).** Given a refresh cookie issued at T, when it is used at T+7 days, then `/auth/refresh` returns 401, and the frontend clears the auth store and routes to login. AC3.5.2 covers only the positive "within 7 days" case.
- **New AC3.6.9 (rotation and storage).** Given a successful refresh, then the new cookie value differs from the old one, the server-side record is keyed by a token identifier, and no raw refresh-token value exists in the database (FR2.5 "not the raw token"; nothing covers this today).
- **New AC3.8.3 (token validation, FR2.10).** Given each protected route, when it is called with no token, an expired token, a token with a tampered signature, a token signed with `alg: none`, or a `reset_token` (AC3.9.4), then it returns 401. [Recommendation: build the route list from the FastAPI router minus an explicit public allow-list, so a new unprotected route fails the test. This is the only reliable test for "every protected endpoint".]
- **AC3.6.5 → extend to logout.** FR2.11 also covers `/auth/logout`. Add: Given a logout request without `X-Requested-With`, or from an origin not on the allow-list, then it is refused and the session stays valid.
- **New AC3.5.5 (cookie attributes).** Given the refresh cookie, then it is `HttpOnly`, its `Max-Age` equals the configured 7 days, and `Secure`/`SameSite`/`Path` come from configuration. [Recommendation for `Secure`/`SameSite`/`Path`. `HttpOnly` is client-stated in `FE-002`.]
- **AC3.9.2 wording.** Replace "reusing the same reset link or token fails" with "reusing the `reset_token` fails". The flow has no link (`AUTH-015`).
- **New AC3.9.5 (reset-token expiry).** Given a `reset_token` issued at T, when it is used at T+10:00, then it is refused. [The window is "~10 minutes" in `AUTH-015`; the exact value should be a setting.]
- **AC3.9.3.** "Every *other* session" conflicts with FR2.12 and `AUTH-015`, which say "every session … on every device". Use FR2.12's wording and its testable form: every refresh cookie issued before the reset returns 401.

#### 1c. Frontend API client: proactive refresh, 401 → refresh → retry, single-flight (`FE-005`, `FE-006`)

- **AC3.6.1** ("refreshed before expiry with no visible interruption") is not observable. Proposed rewrite: Given an access token whose `exp` is T+15:00, then with fake timers no refresh call has been made at T+13:59 and exactly one has been made by T+14:00 (refresh when remaining lifetime ≤ the configured 60 s lead). No request reaches the UI as a 401, and no navigation happens.
- **AC3.5.1.** Drop "briefly". Rewrite as: while the start-up refresh is pending, the loading state is rendered and protected content is not rendered.
- **AC3.6.2 → add three companions:**
  - Given a proactive refresh is already in flight when a request gets a 401, then that request waits on the same refresh (still exactly one refresh call).
  - Given the retried request gets 401 again, then it is not retried a second time: there is exactly one retry and no loop.
  - Given a 401 from `/auth/refresh` itself, then no nested refresh is attempted.
- **New AC3.6.10 (positive clear path, FR3.5).** Given the single shared refresh returns 401, then every request waiting on it rejects, the auth store is cleared exactly once, and the app redirects to login exactly once. The requirements have this AC (FR3 AC 5), but no story does.
- **AC3.6.3 → make fan-out explicit.** Given the shared refresh fails with a network error or 5xx, then waiting requests reject with an error toast and the store keeps the user.
- **New AC3.7.4 (no implicit logout, `WF-002` step 5).** Given page unload, a visibility change or a route change, then no logout call is made and the store is not cleared.
- **AC3.6.6 (two tabs)** can have its behaviour written now while the mechanism waits for Domain Design: Given two tabs holding the same refresh cookie refresh within the same second, then both end with a valid session and the token family is not revoked. That gives Domain Design a failing test to satisfy. Until then the AC is Deferred in traceability, not untested.
- **New AC on US1.3 (`FE-007`, Section 5.3).** Given a UI component that imports the auth API module or reads a token, then the ESLint layering rule fails the CI check. Team practices make this lint-enforced, but no AC checks it.

#### 1d. Identity-check vote (`BR-005` rules 1–5, FR6.3–FR6.5)

The vote is a pure function over three pairwise results (front↔right, front↔left, right↔left). That gives exactly **8 cases**, and all 8 should be ACs, because they are the test-first specification:

| # | F↔R | F↔L | R↔L | Expected `mismatched_angles` | Draft AC |
|---|---|---|---|---|---|
| 1 | ✓ | ✓ | ✓ | `[]` | missing (implicit) |
| 2 | ✓ | ✗ | ✗ | `[left]` | **missing** |
| 3 | ✗ | ✓ | ✗ | `[right]` | AC5.6.1 |
| 4 | ✗ | ✗ | ✓ | `[front]` | **missing** |
| 5 | ✓ | ✓ | ✗ (front is hub) | `[]` per FR6.4 — **source conflict, see §2** | AC5.6.2 |
| 6 | ✓ | ✗ | ✓ (right is hub) | front and left tie on 1 match each → front is reference → `[left]` | **missing** |
| 7 | ✗ | ✓ | ✓ (left is hub) | → `[right]` | **missing** |
| 8 | ✗ | ✗ | ✗ | `[right, left]` | AC5.6.3 |

- **Case 4 matters most.** No current AC ever flags front, so a naive "front is always the reference" implementation passes every AC in the draft. That contradicts `BR-005` rule 2 ("the one with the fewest matches is flagged").
- **Threshold boundary.** Given a pair distance exactly equal to the configured threshold (0.6), then the pair counts as a match. Test at 0.6 − ε, 0.6 and 0.6 + ε. [Assumption: "within the threshold" means ≤. Confirm in functional design.]
- **Recompute (rule 5).** Add a regression AC. Given photos A/A/B (left flagged), when *right* is retaken as B, then the result is `[front]`: the error moves to an angle nobody touched, and nothing carries over. Without this, a stale-merge bug passes.
- **Pending ≠ consistent** [Recommendation]. Given a retake has just uploaded and the fresh identity result has not arrived, then Continue is disabled and no automatic navigation happens. This extends AC5.6.4 to the in-between state, which is the known failure mode for this rule (auto-advancing on a null result).
- **Split AC5.6.4** into a backend AC (the result is recomputed from the current three photos) and a UI AC (no auto-navigation; Continue enabled only when the result is an empty list). They are tested in different suites.
- **409 body (AC6.2.2, AC7.1.2).** Assert that the 409 body's mismatched angles equal the vote function's output for the same photos. Otherwise the server-side re-check could use different logic from the review screen.

---

### 2. Conflicts and ambiguities to surface (not resolve)

- **Hub case (row 5 / AC5.6.2).** `requirements.md` FR6.4 and its AC say that when front matches both others but right↔left do not match, nothing is flagged. The space knowledge file `aidlc/spaces/default/knowledge/photo_identity_validation_spec.md` §3 item 5 says the same case "resolves to a single flagged angle, with front protected". `client_requirements.md` `BR-005` rule 2 says only "front is treated as the reference". There is also a risk argument: "nothing flagged" lets a set pass where two photos disagree, which weakens `BR-004`/`CON-006` (no human review). This needs the human or client to decide.
- **Candidate specifications already in space knowledge.** US4.4, US5.9, US8.6 and US11.3 are marked *Blocked: spec*, and `client_requirements.md` says the specifications "do not exist yet". But `aidlc/spaces/default/knowledge/` holds `onboarding_questionnaire_spec.md` (23 questions, the Q19 branch, exact disclaimer wording, status Draft), `photo_identity_validation_spec.md` (v1.1), `photo_capture_spec.md`, `report_design_spec.md` and `report_template.md`. The human should say whether these are the client's specifications. If they are, the blocked stories become testable now, and AC4.4.1–AC4.4.3 can name concrete checks (Q4 = Feminine → Q19 skipped; the disclaimer text matches exactly).
- **"7 measured features" (AC7.3.1, FR8.3, `FR-007`).** 11 features − Hair, Skin, Neck = 8, not 7. The client wording (Ears "the exception") leaves one feature unaccounted for. AC7.3.1 and AC8.4.1 cannot be tested until the list is named. Surface this to the client.

---

### 3. Criteria that depend on nondeterministic AI output

Principle: the default run tests the *system's handling* of AI output with deterministic fakes. It tests *model behaviour* only in an opt-in evaluation suite that never runs in CI (the project Forbidden rule on paid calls, and AC1.3.3).

| AC | Problem | Proposed testable form |
|---|---|---|
| AC7.4.1 (3–5 sentences, cites a value) | Depends on the real model | Deterministic: the pipeline *validates* model output (11 features present, 3–5 sentences, a measurement value present for measured features). Test with fake responses that pass and fail the checks. Real-model quality goes to the eval suite. |
| **New AC7.4.5** [Recommendation] | No AC covers invalid or malformed AI output | Given the text fake returns malformed structured output, or a narrative that fails validation, then the step is retried up to a configured count, and after that the job ends "failed with reason" (US1.7). Nothing is published half-valid. |
| AC7.4.2 | Good. Tighten it. | Assert on the captured fake payload: neither the *question text nor the answer* of any medical-flagged question appears. Seed canary strings in the fixture answers. |
| **New AC7.4.6** (FR8.4, FR8.5 d) | Multimodal input and personalisation have no AC | The captured payload contains the photos, the measurements, and the user's goal/motivation/liked/disliked answers. |
| AC8.2.3 ("worded as informational") | Not checkable | [Recommendation] Make "consult a qualified professional" static template copy so it can be checked exactly. Tone goes to eval. |
| AC10.1.1 | Depends on the real model | Deterministic: the grounding context sent to the fake contains the stored symmetry score. The answer quality check goes to eval. |
| AC10.2.2 | As written, needs the real model, so it cannot be in the default run | Move it to the opt-in eval suite: N fixed medical/medication prompts, 100% must decline, run before handover. In the default run, assert that the system prompt carries the decline instruction. |
| AC9.1 "still looks like me" | Not automatable | Manual/eval check before handover (`ASM-011`). Automated: the fake is called in edit mode with the user's photo and the configured fidelity parameter (AC9.1.2). |

Add a story convention line: "AI-quality ACs marked *(eval)* run in the opt-in evaluation suite, not the default test run." This keeps the Forbidden rule and the requirement-to-test mapping consistent.

---

### 4. Sad paths and boundaries missing elsewhere

- **Payment.**
  - **New AC6.3.4:** Given the browser returns to the success URL but no webhook has arrived, then the payment is *not* succeeded and Start Analysis stays unavailable. FR7.4 says "only the verified webhook".
  - **AC6.3.2:** Define idempotency by Stripe event id, and add: two *concurrent* deliveries of the same event → one record, enforced by a database constraint.
  - **New AC6.1.3:** Given the configured price changes, then the fake Stripe records the new amount on the next checkout session. The requirements AC asks for the *charged* price; AC6.1.2 checks only the screen.
  - **402/409 precedence** [Recommendation]: unpaid and inconsistent → 402, following FR8.1's order.
  - **Paying twice** (checkout after a succeeded payment) is unspecified. Flag it for Contract Design.
- **Analysis.**
  - **AC7.1.3:** Rewrite as two concurrent start requests → exactly one job, and the second returns the same job id.
  - **New AC7.1.4** (`NFR10` "one analysis per paid report"): Given a completed run, when start is called again, then no new job starts and no vendor call is made.
  - **Missing story (judgment call):** a paid user's analysis job *fails*, for example after a vendor timeout (`NFR5` "errors surfaced"). What does the user see, and can they re-run without paying again? No story covers this. See Positions.
  - **AC7.2.3 (10 minutes):** Name the fake latency profile as a committed test setting, and match NFR4's definition ("all narratives written and all 24 images generated or marked failed"). Add the NFR4 one-time real-vendor timing check as a manual, pre-handover AC.
  - **New AC9.5.4** (FR10.5 "report text never waits on images"): Given an image fake that is still pending, then the narratives are visible.
- **Images.**
  - **AC9.5.1 → exact:** Fake fails attempts 1–3, then succeeds → the image is stored, and there are exactly 4 vendor calls. Fake fails 4 times → the slot shows "not available yet", and there are exactly 4 calls with no 5th.
  - **Manual retry (AC9.5.3)** has no cap, but `NFR10` asks for "a cap on image retries". Say whether manual retries are capped. Also add the failure case: the retry fails → toast, and the slot stays marked.
- **Chat limit (AC10.3.1).**
  - Define "daily": UTC midnight, the user's local midnight, or a rolling 24 h. The boundary test and "the time I can chat again" depend on it.
  - Add: concurrent sends at 49/50 → exactly 50 accepted.
  - Say whether a message whose OpenAI call failed counts toward the limit.
- **Email provider (`NFR5`, `NFR12`).** No AC covers email-send failure at sign-up, login or reset: the user sees an error toast, and the account state is defined. AC1.6.1 proves vendor swap only for images. Add the same swap check for email (NFR12 "configuration and one adapter only").
- **Routing.** AC2.1.3, AC5.7.1 and AC11.1.1 all depend on one "which step has this user reached" decision. [Recommendation] State it once as a truth table: no consent → consent; consent but questionnaire not submitted → questionnaire; photos incomplete or inconsistent → photos; unpaid → payment; paid, not started → start; running → progress; report exists → Home. Reference the table from all three ACs, so one parametrised test covers them.
- **Ownership (AC1.8.1).** "404 or 403" is not a deterministic assertion. [Recommendation: 404, which avoids revealing that the resource exists.] Fix it in Contract Design, and have the AC reference that decision.
- **Consent (AC4.1.1).** This is UI-only. Add: a direct questionnaire API call without stored consent is refused, matching the backend check in AC4.3.3.
- **AC4.2.2** has two outcomes. Split it into "appears" and "is skipped" so both branches get a test.
- **Symmetry label (AC7.5.1).** The label boundaries ("Quite Symmetric", …) are not defined anywhere, so they cannot be tested. Name them as configuration or a table in functional design.

---

### 5. FR/NFR coverage gaps

| Requirement | Gap | Proposal |
|---|---|---|
| FR2.15 / `AUTH-001` | Traced by US3.1, but no AC checks it | AC on US1.4: the dependency audit fails if an auth-as-a-service SDK appears in either lockfile |
| FR2.11 (logout CSRF) | Only refresh is covered | See 1b |
| FR3.5 (refresh 401 → login) | No story AC | AC3.6.10 |
| FR3.6 / `FE-007` | No AC for lint-enforced layering | See 1c |
| NFR4 (real-vendor timing) | Missing | Manual pre-handover AC on US7.2 |
| NFR7 (docstrings, layering lint) | Not in any AC | Add to US1.3 |
| **NFR8** (traceability list, Playwright E2E) | **No story covers it** | New enabler **US1.9** [Recommendation]: "Requirement-to-test map and E2E journeys". ACs: (a) every `FR-*`/`AUTH-*`/`BR-*`/`FE-*` ID maps to ≥1 test, or to N/A or Deferred with a reason, and CI fails on an unmapped ID; (b) the Playwright journeys sign-up/login and photos → payment → report pass on a phone-sized and a desktop viewport |
| **NFR9** | AC11.7.3 covers only toasts and dialogs | Add to US1.9 or US11.7: axe reports no WCAG 2.1 AA violations on the main screens (landing, auth, questionnaire, photos, payment, report, Home, chat, settings). Browser matrix: Playwright Chromium, WebKit and Firefox (Edge is Chromium-based) |
| NFR12 | Swap-by-configuration is proven only for images | Extend AC1.6.1 to email |
| Coverage table | "NFR1–NFR12 See `traceability.json`", but no `traceability.json` exists in the stage folder | Produce it, or list the NFR mappings inline |

---

### 6. Testability of the walking skeleton

- US3.1 depends on **US1.6** (the email fake), and US3.8 depends on **US3.5**. Neither is in the skeleton list, so the list as drafted cannot be built and verified on its own. Either add them to the skeleton or narrow the dependencies to what the skeleton needs: the email fake, and `/auth/me` without session restore.
- The skeleton's Verification Command (sign-up → OTP → login → `/auth/me`) needs the test to *read the emailed code*. Add an AC to US1.6: in test configuration, the email fake stores sent codes where the test harness can read them. That capability can never be enabled by production configuration, and the stored codes must not appear in logs (AC1.8.3).
- **AC1.3.3 → make it enforceable.** The backend test run blocks outbound network, and the frontend mock layer errors on any unhandled request. "No request is made" then fails loudly instead of silently.
- **AC1.8.3.** Use canary values in fixtures (sentinel answer text, sentinel image bytes) and assert on the captured logs. This turns "no sensitive data in logs" into an exact check.

## Positions

- AGREE: Given/When/Then with stable `AC{g}.{s}.{n}` IDs, journey grouping, enabler stories and the engine-versus-blocked-content split. These make nearly every story independently testable with fakes.
- AGREE: AC5.6.1, AC5.6.3, AC5.6.5, AC6.3.3, AC6.4.1, AC7.5.2, AC8.1.1, AC8.1.3 and AC10.3.2 are already concrete pass/fail checks and should stay as written.
- OBJECT: The identity-vote ACs never flag front and skip both non-front hub cases, so a "front is always the reference" implementation passes every AC. Add the full 8-case table (1d). Knowledge dispute (`BR-005` rule 2 is explicit).
- OBJECT: AC5.6.2 (front hub → nothing flagged) conflicts with `aidlc/spaces/default/knowledge/photo_identity_validation_spec.md` §3.5 (one non-front angle flagged) and weakens `BR-004`. Knowledge dispute between sources. Surface it to the human or client rather than settling it in round 2.
- OBJECT: The OTP ACs (AC3.2.x, AC3.3.x, AC3.9) leave boundary inclusivity, single use, resend-invalidation and failure-counter scope undefined, so the test-first OTP service cannot start from failing tests. Knowledge dispute (the precision a test-first module requires).
- OBJECT: Backend token ACs are missing: 15-minute access expiry, 7-day refresh expiry, rotation and no raw token stored, logout CSRF, and the all-routes token-validation check. Knowledge dispute (FR2.5, FR2.10, FR2.11 are untested as drafted).
- OBJECT: AC3.6.1 and AC3.5.1 are not observable ("no visible interruption", "briefly"), and the frontend has no AC for refresh-401 → clear and redirect once, retry-once, or no-implicit-logout. Knowledge dispute (`FE-005`, `FE-006` test-first module).
- OBJECT: AC7.4.1, AC8.2.3, AC10.1.1 and AC10.2.2 assert real-model behaviour. In the default run that would break the Forbidden paid-call rule. Split each into a deterministic fake-based check plus an opt-in *(eval)* check. Knowledge dispute.
- OBJECT: AC7.3.1 "the 7 measured features" is unnamed, and 11 − 3 = 8, so it cannot be tested. Surface this to the client. Knowledge dispute (source ambiguity in `FR-007`).
- OBJECT: US4.4, US5.9, US8.6 and US11.3 are marked blocked although candidate specifications exist in `aidlc/spaces/default/knowledge/`. The human must say whether those documents are the client's specifications. Judgment call.
- OBJECT: No story covers a paid user's analysis job that fails (free re-run versus other handling, bounded by `NFR10`). Judgment call (scope and cost appetite), but `NFR5` requires defined behaviour.
- OBJECT: The chat daily limit has no definition of "day" or of whether failed calls count, and manual image retries have no cap despite `NFR10`. Judgment call (product choice); each needs a decided value before its boundary tests can be written.
- OBJECT: NFR8 (requirement-to-test map, Playwright journeys), NFR9 (axe on the main screens, two viewports), NFR12 (email swap) and NFR4 (real-vendor timing) have no story ACs, and the coverage table points to a `traceability.json` that does not exist. Knowledge dispute (upstream NFRs uncovered).
- OBJECT: The walking-skeleton list omits US1.6 and US3.5, which its own stories depend on, and has no AC letting a test read the emailed OTP. Knowledge dispute (the skeleton cannot be verified end to end as listed).
