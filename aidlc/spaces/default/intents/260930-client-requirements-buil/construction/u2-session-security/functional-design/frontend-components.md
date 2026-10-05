# Frontend Components — U2 Session Security

U2 extends the U1 frontend: the auth store, the API client, and the sign-up, code, login and home pages. The layering is fixed: UI → auth store → API client → backend. UI components read state through `useAuth()` selectors and call store actions only. They never call auth endpoints or see tokens (FE-007, U1 BR5.3).

## Component hierarchy

```text
RootLayout (reads CSP nonce; mounts providers)
├── ApiConfigProvider                      (U1)
├── AuthBootstrap        NEW — runs WF-U2-2 restore once per tab; renders FullPageLoader while initializing
├── ToastRegion          NEW — single live-region host (top-right; under header on phones)
├── ConfirmDialogHost    NEW — single dialog instance driven by confirm()
└── Routes
    ├── /signup, /login                     (U1) + SecurityNotice when signedOutReason = security
    ├── /verify                             (U1) + ResendCodeButton (countdown) replaces "start again"
    ├── /forgot-password                    NEW — ForgotPasswordForm
    ├── /forgot-password/verify             NEW — reuses CodeForm with purpose password_reset
    ├── /reset-password                     NEW — ResetPasswordForm (reset token in page memory)
    ├── ProtectedRoute                      NEW — waits for initializing; signedOut → /login
    │   ├── /home                           (U1) + header UserMenu with "Log out"
    │   └── /settings/password              NEW — ChangePasswordForm
```

## Store (`lib/auth/store.ts`, extended)

| State | Type | Notes |
|---|---|---|
| `status` | `initializing / signedIn / signedOut` | Starts as `initializing` (BR6.1) |
| `accessToken`, `accessTokenExpiresAt` | memory only | Never exposed to components |
| `user` | `User` profile | Selector `useAuth().user` |
| `signedOutReason` | `logout / session_expired / security` | Read by `SecurityNotice` |

| Action (UI may call) | Does |
|---|---|
| `restore()` | WF-U2-2 (called once by `AuthBootstrap`) |
| `logout()` | WF-U2-6 steps 3–4 (UI calls it only after `confirm()`) |
| `resendCode(email, purpose)`, `requestPasswordReset(email)`, `verifyResetCode(email, code)`, `resetPassword(token, newPassword)`, `changePassword(current, next)` | Thin wrappers over `lib/auth/api.ts` returning typed results for forms |

Internal only (not exported to UI):
- `refreshCoordinator`: single-flight plus the cross-tab lock and broadcast (WF-U2-3, WF-U2-4). Built test-first.
- `scheduleProactiveRefresh()`.

## API client (`lib/api/client.ts`, extended)
- Its 401 handler acts only on `error.code === "NOT_AUTHENTICATED"`. It awaits `refreshCoordinator.refresh()` and retries once, carrying a `retried` flag on the request (BR6.3, BR6.4).
- Refresh and logout calls go through `client.raw()`, which bypasses the 401 handler. They always send `X-Requested-With: XMLHttpRequest` and `credentials: "include"`.
- On a network error or 5xx from refresh, waiting requests reject with an `ApiError` whose `code` is `NETWORK_ERROR` or `UPSTREAM`, and the store raises an error toast (BR6.5).

## Forms and validation

| Form | Fields and client rules | Server errors mapped inline |
|---|---|---|
| ResendCodeButton | Disabled with a countdown until `resendAvailableAt`; becomes available by itself | `CODE_RESEND_COOLDOWN` (re-sync countdown), `CODE_LOCKED` (show "Try again in mm:ss") |
| ForgotPasswordForm | email (format) | none: always the same neutral message, no outcome toast (BR4.1) |
| ResetPasswordForm | newPassword (live rule hints), confirm (match) | `VALIDATION_FAILED` → newPassword; `RESET_TOKEN_INVALID` → page message with a link back to `/forgot-password` |
| ChangePasswordForm | currentPassword (required), newPassword (rule hints), confirm (match, BR5.2) | `INVALID_CREDENTIALS` → currentPassword + error toast; `VALIDATION_FAILED` → newPassword |

## Shared UI components
- **Toast service** (`components/feedback/toast.ts` + `ToastRegion`): `success` / `error`, live regions, 5 s auto-dismiss for success, persistent errors, at most 3 stacked, positioned under the header below 640 px (BR7.1, BR7.2, BR7.5).
- **Confirm dialog** (`components/feedback/confirm.ts` + `ConfirmDialogHost`): an accessible modal with a focus trap, Escape to cancel, return focus, and a named confirm button (BR7.3). Built on the shadcn/ui `AlertDialog`.
- **FieldError**: text linked with `aria-describedby`, `aria-invalid` set on the input (BR7.4). Every U1 form is switched to it.
- **FullPageLoader**: an accessible spinner (`role="status"`, label "Restoring your session") shown while `status = initializing`.
- **SecurityNotice**: a one-time banner on `/login`: "You were signed out for your security. Please log in again." (BR6.7).

## data-testid naming (new)
`resend-code-button`, `forgot-password-email-input`, `forgot-password-submit-button`, `reset-password-new-input`, `reset-password-confirm-input`, `reset-password-submit-button`, `change-password-current-input`, `change-password-new-input`, `change-password-confirm-input`, `change-password-submit-button`, `user-menu-button`, `user-menu-logout`, `confirm-dialog`, `confirm-dialog-confirm`, `confirm-dialog-cancel`, `toast-region`, `security-notice`, `session-loader`.
