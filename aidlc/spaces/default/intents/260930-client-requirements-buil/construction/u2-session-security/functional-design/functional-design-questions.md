# Functional Design — U2 Session Security — Questions

U2 completes sign-in:
- resend and lockout;
- staying signed in across reloads;
- silent refresh with reuse detection and CSRF checks;
- logout;
- password reset and change;
- two-tab coordination;
- the app-wide toast and confirmation dialog.

The client document fixes most of the rules (`AUTH-010`–`AUTH-016`, `FE-002`–`FE-007`). The domain design already settled two points: tabs coordinate refresh with a browser lock, and the server keeps reuse detection strict (ADR-006). The reset token is an opaque value stored only as a hash (`PasswordResetToken`). Three behaviours remain open.

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — "Resend code" for an email with no matching account
`/auth/resend-code` takes an email and a purpose. Sign-up already reveals whether an email is registered (client rule FR2.1), but resend doesn't need to.

A. Always answer the same way ("code sent", same shape) whether or not a matching unverified sign-up or account exists. An email goes out only when there is a real account in the right state. Cooldown and lockout still apply to real accounts (Recommended)
B. Return an error when no matching account exists
X. Other (please specify)

[Answer]: A

### Question 2 — Changing the password while signed in
The client requires that the current session stays active (`AUTH-016`). The client says nothing about the user's other devices.

A. Keep the current session and sign out every other device, because a password change often follows a suspected compromise **[Recommendation]** (Recommended)
B. Keep every session, including other devices (only what the client states)
X. Other (please specify)

[Answer]: A

### Question 3 — Logging out with the app open in several tabs
A. Logging out in one tab immediately signs out every open tab (a broadcast to the other tabs), so no tab keeps showing private data (Recommended)
B. Other tabs find out only when their next refresh fails (up to 15 minutes later)
X. Other (please specify)

[Answer]: A
