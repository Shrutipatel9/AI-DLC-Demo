# Web app (Next.js)

Next.js 16 (App Router) · TypeScript strict · Zustand · Tailwind CSS 4 · react-hook-form + zod · pnpm

> Next.js 16 renamed `middleware.ts` to `proxy.ts`. The per-request CSP lives in
> `src/proxy.ts`. Bundled Next.js docs are in `node_modules/next/dist/docs/`.

## Setup

```bash
cp .env.example .env.local      # API_ORIGIN=http://localhost:8000
pnpm install
pnpm dev                        # http://localhost:3000 (the API must run on :8000)
```

## Commands

| Task                                                              | Command                                                                                                  |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Lint (ESLint, security plugin, layering rules)                    | `pnpm lint`                                                                                              |
| Format / check                                                    | `pnpm format` / `pnpm format:check`                                                                      |
| Types                                                             | `pnpm typecheck`                                                                                         |
| Unit and component tests with coverage (lines >= 80%)             | `pnpm exec vitest run --coverage`                                                                        |
| Production build / run                                            | `pnpm build` / `pnpm start`                                                                              |
| Bundle budget (auth, onboarding, photo, payment routes <= 200 KB) | `pnpm size-check` (after `pnpm build`)                                                                   |
| End-to-end journeys (needs Compose, the API, and `pnpm start`)    | `pnpm exec playwright test` (skeleton, session, onboarding, photos, payments, analysis incl. AI Visuals) |
| Photo tests only (U4)                                             | `pnpm exec vitest run src/components/photos src/lib/photos src/app/photos`                               |
| Payment tests only (U5)                                           | `pnpm exec vitest run src/components/payments src/lib/payments src/app/payment`                          |
| Analysis tests only (U6)                                          | `pnpm exec vitest run src/components/analysis src/lib/analysis src/app/analysis`                         |
| AI Visuals tests only (U7)                                        | `pnpm exec vitest run src/components/visuals src/app/visuals`                                            |
| Regenerate API types from the backend                             | `bash ../scripts/export-openapi.sh`                                                                      |

Vitest replaces `fetch` with a stub that fails any request a test did not handle, so unit
tests can never reach the network.

## Environment keys

| Key            | Example                 | Notes                                                                                                                                                                              |
| -------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `API_ORIGIN`   | `http://localhost:8000` | Read by the **server at request time** (root layout and proxy), not baked into the build, so one build serves every environment. Used for the API client and the CSP `connect-src` |
| `WEB_BASE_URL` | `http://localhost:3000` | Playwright only                                                                                                                                                                    |
| `MAILPIT_URL`  | `http://127.0.0.1:8025` | Playwright only: where the journey reads emailed codes                                                                                                                             |

No secrets belong in the frontend.

## Layer map (client Section 5.3)

```text
UI (src/app, src/components)
  └─ uses only useAuth() / useAuthActions() from "@/lib/auth"
Zustand auth store + actions (src/lib/auth)
  └─ store.ts: status, access token, profile, sign-out reason, generation, code step —
     in memory only (no persist, no Web Storage)
  └─ actions.ts / api.ts: sign up, log in, verify, resend, who-am-I, reset, change password
  └─ session.ts: the tab's refresh coordinator, restore and logout (private)
  └─ refresh-coordinator.ts: single-flight refresh, cross-tab lock and broadcast (private)
API client (src/lib/api/client.ts)
  └─ the only fetch caller: Bearer token, credentials: "include", X-Requested-With,
     30 s timeout, typed ApiError { code, details, requestId }; a 401 NOT_AUTHENTICATED
     joins the shared refresh and retries once (apiRaw skips this for refresh/logout)
Backend auth APIs (FastAPI)
```

ESLint enforces this: UI files may not import `@/lib/auth/*` internals or the API client, may
not call `fetch`, and may not touch `localStorage` or `sessionStorage`. Only `src/lib/auth/*`
may import the store. `zustand/middleware`'s `persist` is banned.

Other folders:

- `src/proxy.ts` and `src/lib/config/csp.ts`: the nonce-based CSP.
- `src/lib/config/api-config.tsx`: the runtime API origin.
- `src/components/ui`: shadcn-style primitives.
- `src/styles/tokens.css`: design tokens (one place to rebrand).
- `src/lib/api/types.gen.ts`: generated from the backend OpenAPI document. Never edit it by hand; CI fails on drift.
- `src/lib/photos`: the photo endpoints, set rules, file preflight and camera wrappers (U4).
- `src/components/photos`: the photo screens (U4).
- `src/lib/payments`: the payment endpoints, price formatting, the checkout redirect and the
  confirmation polling hook (U5).
- `src/components/payments`: the payment and confirming screens (U5).
- `src/lib/analysis`: the analysis endpoints and the polling hook (`useAnalysisProgress`, U6).
- `src/components/analysis`: the progress screen (`/analysis`, U6).
- `src/lib/images`: the AI image endpoints and the polling hook (`useVisuals`, U7).
- `src/components/visuals`: the AI Visuals screen (`/visuals`, U7).

## Session (U2)

- **Restore.** `AuthBootstrap` (root layout) calls `restore()` once per tab: `POST
/auth/refresh` with the httpOnly cookie, then `GET /auth/me`. Protected pages
  (`ProtectedRoute`) show `FullPageLoader` meanwhile, never the login form; a network error or
  5xx shows Retry instead of signing out.
- **Renewal.** The coordinator refreshes one minute before the access token expires. Any
  number of concurrent 401 `NOT_AUTHENTICATED` responses share one refresh, and each request
  is retried once. A refresh 401 signs the tab out once and tells the other tabs; a network
  error or 5xx is retried once with the same `X-Refresh-Attempt` id (so the server can recover
  a lost response) and then shows one error toast, keeping the user signed in.
- **Tabs.** Every refresh takes the Web Lock `auth-refresh`; a result another tab broadcast on
  the `auth` BroadcastChannel in the last 5 s is adopted instead of calling the server. Without
  Web Locks, tabs use a BroadcastChannel claim; without both, each tab refreshes alone. Logout
  takes the lock, bumps a store generation (late refresh results are discarded), revokes the
  session family on the server and broadcasts `signedOut`, so every tab signs out.
- **Reset token.** The single-use reset token stays in `src/lib/auth/actions.ts` memory; UI
  code only asks `hasResetToken()`.
- **Diagnostics.** `src/lib/auth/session-log.ts` logs the refresh failure class, sign-out
  reason and lock mode to the console in development only; never tokens or ids.

## Photos (U4)

`/photos` (`src/components/photos/photo-flow.tsx`): the 7 rules with example illustrations,
then one step per configured angle (from `GET /photos/requirements`, so the angle set is a
backend setting), then the review screen.

- **Upload and camera.** File upload is always offered; the camera button appears only when
  the browser has `getUserMedia`. The live view is mirrored like a selfie with the angle's
  outline over it; the captured frame is not mirrored, so the stored photo turns the way the
  person really turned. A denied or missing camera shows a message, never a broken view.
  `src/lib/photos/files.ts` refuses wrong types and files over the limit before uploading; the
  server checks again and decides.
- **Uploads** go through the single API client as multipart `FormData` (`apiRequest` sends a
  `FormData` body as it is). Private photos are read with `apiBlob` (Bearer token) and shown
  from `blob:` URLs, which the CSP allows in `img-src`; nothing is a public image URL.
- **State rules** ([IV] §1, §6). The server's PhotoSet is the only truth and every upload
  answer replaces it. The moment an upload starts, the same-person result is reset to
  "pending", which is never treated as consistent. The review screen never navigates on its
  own: Continue is disabled with its reason while a photo is flagged or a result is pending,
  and only a click leaves the screen.
- **Messages** (`src/components/photos/messages.ts`): each rejection code becomes a
  photo-focused fix ("Move closer so your face fills more of the frame"), never a comment on
  the person. The pose message names the angle and repeats its turn instruction.
- **Example images** are simple drawings (`illustrations.tsx`) until the client supplies
  its own photos.
- **Browser journey** (`e2e/photos.spec.ts`): synthetic face renders in `e2e/fixtures/photos`
  (no real person), checked by the real MediaPipe model in the API. The API must run with
  `FACE_LANDMARK_OVERRIDES_FILE=tests/fixtures/faces/overrides.json` for the
  different-person scenario (see `scripts/verify.sh`).

## Payment (U5)

`/payment` (`src/components/payments/payment-screen.tsx`), reached from the photo review's
Continue: the configured price and currency from `GET /payments/offer` (formatted with the
currency's own decimals), what payment unlocks, and that the analysis starts only on "Start
Analysis". No result or partial content is shown. "Pay" calls `POST /payments/checkout` (the
server re-checks the photos: a 409 shows the reason with a link back to `/photos`) and then
navigates the whole window to the returned hosted Checkout URL (`goToCheckout`, http(s) only).

- `/payment/success` (`payment-confirmation.tsx`): "Confirming your payment" until
  `GET /payments/status` (polled every 2 s) reads `paid`. Coming back here proves nothing:
  only the server's verified webhook changes the status. "Start Analysis" stays disabled with
  its reason until then; the confirmation updates the screen without a reload and is announced
  in an `aria-live` region. After `confirmWaitSeconds` the screen says the payment is still
  being confirmed, that the user won't be charged twice and can safely leave. "Start Analysis"
  never runs by itself; until U6 adds the analysis start it returns to the home page.
- `/payment/cancel`: the payment screen again, saying nothing was charged.
- **Browser journey** (`e2e/payments.spec.ts`): runs with the API's Stripe fake
  (`PAYMENT_PROVIDER=fake` from `scripts/ci-env.sh`): the payment screen, the fake's hosted
  test page on the API, "Pay", "confirming", then "confirmed" when the fake's signed webhook
  arrives; and "Cancel" back to the payment screen. The expected price comes from
  `REPORT_PRICE_AMOUNT` / `REPORT_PRICE_CURRENCY` (2900 USD by default).

## Analysis progress (U6)

"Start Analysis" on the payment confirmation (`src/components/payments/payment-confirmation.tsx`)
is the only thing that starts the analysis: it calls `POST /analysis/runs` and opens `/analysis`
(a 409 about the photos shows its message and goes to `/photos`). `/analysis`
(`src/components/analysis/analysis-progress.tsx`) polls `GET /analysis/runs/current` every
2 s while the run is going: each step shows done / in progress / waiting in words, a polite
live region announces changes without moving focus, the expected wait comes from the server, and
leaving and coming back reads the same run. When ready it offers "View my report" (to `/home`
until the report screens exist). After a failure it explains in plain language and offers one free
"Try again for free"; after a second failure it points to support.

- **Browser journey** (`e2e/analysis.spec.ts`): needs the background worker with the AI fake
  (`scripts/verify.sh` and `scripts/verify-skeleton.sh` start it): a paid user starts the analysis,
  the steps advance, "View my report" appears (the `@checkpoint` scenario); and a failed run
  (the worker is told through `AI_FAKE_CONTROL_DIR`) is explained and completed by the free re-run.

## AI Visuals (U7)

`/visuals` (`src/components/visuals/visuals-screen.tsx`) shows 5 hairstyles, 5 outfits and the
four-card aging stack (the user's own front photo first, then +3, +5 and +10 years). It reads
`GET /images` through `@/lib/images` and polls every 3 s while images are being created. Every
generated image is labelled "AI-generated illustration"; private images load as blobs through
the API client. An image that is not available yet shows "Not available yet" and a Retry button
(`POST /images/{slotId}/retry`); a failed retry shows an error toast and keeps the slot marked,
and the button is disabled once the server reports no retries left. Until the report screens
(U8) add header navigation, the screen is linked from the finished progress screen and Home.

- **Browser journeys** (`e2e/analysis.spec.ts`): the `@checkpoint` journey also opens `/visuals`
  and sees the 13 labelled images; a second scenario makes every image fail through the worker's
  `fail-image` control file, then retries one image back.

## Feedback components (U2, used by every later unit)

- `src/components/feedback/toast.tsx`: `toast.success(message)` (role `status`, 5 s) and
  `toast.error(message)` (role `alert`, stays until dismissed), each with a close button; the
  region (`src/components/ui/toaster.tsx`) shows at most three, below the header on phones.
- `src/components/feedback/confirm.ts` + `confirm-dialog.tsx`: `await confirm({ title, body,
confirmLabel })` for every destructive action. Focus starts on Cancel, Tab is trapped, Escape
  cancels, focus returns to the opener, and the confirm label must name the action.
- `src/components/ui/form-field.tsx`: `FormField` / `FieldError` for inline errors linked by
  `aria-describedby` with `aria-invalid` on the input.
