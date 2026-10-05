# Code Summary — U3 Onboarding (Consent and Questionnaire)

## What was built
- **Backend `app/onboarding/`** (US4.1–US4.4):
  - versioned consent (D2);
  - the questionnaire definition as seed data `data/questionnaire_v1.json`, built from [QS] (D1, D5);
  - branching (`showIf`) and follow-ups;
  - per-answer saves (D3);
  - submit with the required-question check, then the server-side disclaimer check (BR-003);
  - the public read port `get_non_medical_answers` (D4, ADR-007), plus `get_onboarding_state` and `require_submitted_questionnaire` for later units.
- **Migration** `0003_u3_onboarding`:
  - tables `consent_records`, `questionnaire_definitions` and `questionnaire_responses`;
  - a clean downgrade.
- **Endpoints** (contract C1): `GET/POST /onboarding/consent`, `GET /onboarding/questionnaire`, `GET /onboarding/response`, `PUT /onboarding/response/answers/{questionId}` and `POST /onboarding/response/submit`.
  - All are protected and answer with `Cache-Control: no-store`.
  - The medical flag and the client notes are never sent to the browser.
- **Frontend `/onboarding`** (D6):
  - a consent step, then one question per screen;
  - the input follows the question type: text, single choice, grouped multi-select, or Yes/No with a follow-up;
  - Back/Next, the progress "Question N of M" (it follows branching), and resume at the first unanswered question;
  - the disclaimer, using the exact [QS] §4 wording, with Submit disabled and the reason shown, and the "I can't confirm" supportive panel;
  - toasts, `FieldError` and `data-testid` attributes.
- **Home** links to the questionnaire until it is submitted. The OpenAPI types were regenerated.
- **E2E** `e2e/onboarding.spec.ts`:
  - the full journey tagged `@checkpoint` (Q4 = Masculine shows Q19, 23 questions);
  - the branch, resume and supportive-message journey (Q4 = Feminine, 22 questions);
  - axe checks on every screen.
- **Wiring:**
  - CI, `verify.sh` and `verify-skeleton.sh` run `tests/onboarding` and the onboarding spec;
  - `size-check` covers `/onboarding`;
  - import-linter has three new onboarding contracts;
  - CORS allows `PUT`.

## Verification
- `bash scripts/verify-skeleton.sh`: exit 0 in 90 s (budget 110 s), 6 Playwright checkpoint scenarios.
- **Backend:**
  - tests: 69 in `tests/onboarding`, 431 in the whole suite;
  - whole-app line coverage: 98%; onboarding modules 91–100%.
- **Frontend:**
  - tests: 37 new, 179 in the whole suite;
  - line coverage: 95.8%.
- **Gates:**
  - `/onboarding` bundle: 170.8 KB gzipped (limit 200 KB);
  - ruff, mypy `--strict`, import-linter, ESLint, Prettier and tsc are clean.

## Decisions and deviations ([Decided by delivery team] unless noted)
1. **Question types are `text`, `single`, `multi` and `yesno`** (contract C1 enum and [QS] §2). Step 4 mentions a "scale" type, but no [QS] question needs one, so it was not added. Q20 and Q21 are ordered single choices.
2. **New error code `QUESTIONNAIRE_ALREADY_SUBMITTED` (409).** C1 documents a 409 for saving or submitting after submission, but C11 has no code for it. This is a contract gap to confirm.
3. **A consent to an out-of-date text version answers 409 with code `CONSENT_REQUIRED`** and detail reason `CONSENT_VERSION_CHANGED`. This avoids inventing another code.
4. **Additive response fields:** `agreementText` (the configured checkbox statement), `supportUrl` (optional, from `ONBOARDING_SUPPORT_URL`; no link is invented), and `answers` returned as `{value, followUpText}` per question.
5. **Required questions:** every question is required except Q7 (multi-select with no "none" option in [QS]) and Q23 ("Anything else"). Follow-ups are optional.
6. **AC4.3.2 is partly deferred:** after submit, the user sees a submitted state with a link home. The photo requirements screen arrives with U4.
7. **The definition is stored on first use** (`INSERT … ON CONFLICT DO NOTHING`), not by the migration. A stored version whose content differs from its file is refused, so changes need a new version.
8. **`tests/identity/test_csrf_cors.py`:** the pinned CORS method set now includes `PUT`, because the contract requires it.

## Open with the client (kept as `[Open — client]` in the seed)
- The Q9/Q11 follow-up shape.
- The Q19 condition.
- The consent wording.
- The supportive-message wording.
- The medical-flag interpretation of FR-008(f).

## Not done
- Nothing in the plan is left undone apart from deviation 6. Nothing is committed or pushed (D7).
