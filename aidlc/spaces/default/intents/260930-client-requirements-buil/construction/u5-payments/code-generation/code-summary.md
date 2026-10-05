# Code Summary — U5 Payment

## What was built
- **Backend `app/payments/`:**
  - the Stripe adapter (one-time hosted Checkout with inline `price_data`, an idempotency key, timeouts and retries from config);
  - a dev/test-only fake provider with a hosted test page that sends a signed webhook;
  - migration `0005_u5_payments`;
  - endpoints: offer, checkout, status, and the webhook at `POST /payments/stripe/webhook` (raw body, signature checked, idempotent by event id under a database constraint);
  - the paywall port `require_paid`, and `paid_photo_snapshot` (payment is checked first and answers 402; the photo check then answers 409).
- **Frontend:** `/payment`, `/payment/success` (polling with a live "confirming" → confirmed update) and `/payment/cancel`. Photo review Continue now goes to `/payment`.
- **Browser test:** `e2e/payments.spec.ts` (pay journey tagged `@checkpoint`, plus cancel) on desktop and phone, with axe checks.
- The full file list is in `source-manifest.json`.

## Key decisions ([Decided by delivery team] unless noted)
1. **Followed the contract:**
   - webhook path `/payments/stripe/webhook`;
   - payment status values `pending|succeeded|failed`;
   - status response `none|pending|paid`, plus `confirmWaitSeconds`.
2. **Price configuration:** `REPORT_PRICE_AMOUNT` and `REPORT_PRICE_CURRENCY` are required with no default, because the price is still open (OQ-002). A developer's existing `.env` must add both.
3. **Checkout order:**
   - already paid gives 409;
   - then the photo check runs fresh, and a mismatch gives 409 with the U4 angles;
   - a pending row is committed before Stripe is called;
   - if Stripe fails, the answer is 502/504 with "not charged".
4. **The fake provider:** refused outside dev/test, left out of OpenAPI, and its webhook arrives after a short delay.
5. **"Start Analysis":** enabled once paid; it goes to `/home` until U6 replaces that link (TODO U6).
6. **What payment unlocks:** the offer copy is `[Recommendation: copy]`.

## Risks to surface
- Two checkouts started by one user can both be paid. Both are recorded, and refunds are manual.
- The 402 for start-analysis and report is proven at the port level until U6/U8 add those endpoints.

## Tests
- **Backend:** 684 passed, 98.18% line coverage.
- **Frontend:** 260 passed, 96.35% line coverage.
- **Static checks:** lint, mypy, tsc, import-linter, gitleaks and pip-audit are clean.
- **Checkpoint:** `bash scripts/verify-skeleton.sh` exited 0 in 60 s, with 5 browser journeys.
