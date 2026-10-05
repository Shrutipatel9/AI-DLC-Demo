# Entities — U2 Session Security

U2 adds one entity (`PasswordResetToken`) and adds lifecycle behaviour to two that U1 created (`RefreshSession`, `VerificationAttemptCounter`). `User` and `OneTimeCode` are reused unchanged; `OneTimeCode.purpose` already allows `password_reset`. All entities belong to the Identity component (`inception/domain-design/components.md`). The model is technology-agnostic and uses logical types only.

```yaml
entities:
  - name: RefreshSession
    description: Server record of one issued refresh token, created by U1. U2 adds rotation, reuse detection and revocation. The cookie carries tokenId plus a secret; only a hash of the secret is stored.
    attributes:
      - { name: tokenId, type: uuid, required: true, unique: true }
      - { name: secretHash, type: string, required: true, constraints: "hash of the cookie secret; never the raw token (AUTH-010)" }
      - { name: userId, type: uuid, required: true, references: User.id }
      - { name: familyId, type: uuid, required: true, constraints: "one family per sign-in; every rotation stays in the family" }
      - { name: parentTokenId, type: uuid, required: false, references: RefreshSession.tokenId, constraints: "set on the session created by a rotation" }
      - { name: issuedAt, type: timestamp, required: true }
      - { name: expiresAt, type: timestamp, required: true, constraints: "issuedAt + configured lifetime (7 days); each rotation issues a fresh 7-day session" }
      - { name: rotatedAt, type: timestamp, required: false, constraints: "set when this session is exchanged for a child; a rotated session can never be exchanged again" }
      - { name: revokedAt, type: timestamp, required: false }
      - { name: revokedReason, type: enum, required: false, allowed: [logout, reuse_detected, password_reset, password_changed], constraints: "set together with revokedAt" }
    constraints:
      - "A session is usable only when rotatedAt, revokedAt are empty and now < expiresAt"
      - "revokedAt and revokedReason are both set or both empty"
      - "At most one usable session per family at any moment (the newest child)"
    relationships:
      - { to: User, cardinality: "many to 1", direction: "session belongs to user" }
      - { to: RefreshSession, cardinality: "0..1 to 0..1", direction: "child rotated from parent" }

  - name: PasswordResetToken
    description: Single-use proof that a reset code was verified. It authorises exactly one password change within a short window. Opaque random value; only its hash is stored.
    attributes:
      - { name: resetTokenId, type: uuid, required: true, unique: true }
      - { name: userId, type: uuid, required: true, references: User.id }
      - { name: tokenHash, type: string, required: true, unique: true, constraints: "hash of the opaque token; the raw token exists only in the verify-code response" }
      - { name: issuedAt, type: timestamp, required: true }
      - { name: expiresAt, type: timestamp, required: true, constraints: "issuedAt + configured window (initially 10 minutes, AUTH-015)" }
      - { name: usedAt, type: timestamp, required: false, constraints: "set when the password is reset; a used token never works again" }
    constraints:
      - "Issuing a new reset token for a user makes earlier unused ones unusable (usedAt set to the issue time)"
    relationships:
      - { to: User, cardinality: "many to 1", direction: "token belongs to user" }

  - name: VerificationAttemptCounter
    description: Failed-code counter per account and purpose, created by U1. U2 adds the user-visible lockout, the resend refusal during lockout and the password_reset purpose.
    attributes:
      - { name: userId, type: uuid, required: true, references: User.id }
      - { name: purpose, type: enum, required: true, allowed: [signup, login, password_reset] }
      - { name: failedCount, type: integer, required: true, default: 0, min: 0 }
      - { name: lockedUntil, type: timestamp, required: false }
      - { name: lastSentAt, type: timestamp, required: false, constraints: "drives the 60-second resend cooldown" }
    constraints:
      - "Primary identity is (userId, purpose)"

  - name: ClientSession
    description: Frontend-only, in-memory auth state per browser tab (not persisted, not stored on the server). Listed so that the store states are part of the design.
    attributes:
      - { name: status, type: enum, required: true, allowed: [initializing, signedIn, signedOut], default: initializing }
      - { name: accessToken, type: string, required: false, constraints: "memory only (FE-002)" }
      - { name: accessTokenExpiresAt, type: timestamp, required: false }
      - { name: user, type: object, required: false, constraints: "the User profile from /auth/me or the session response" }
      - { name: signedOutReason, type: enum, required: false, allowed: [logout, session_expired, security], constraints: "drives the message on the login screen (AC3.6.4)" }
    constraints:
      - "Never written to localStorage, sessionStorage, IndexedDB or a persisted store"
```

## Summary
- **RefreshSession** gains rotation (`rotatedAt`, `parentTokenId`), reuse detection and revocation with a reason. Each sign-in starts a new family.
- **PasswordResetToken** is new: an opaque, hashed, 10-minute, single-use token that is issued only after the reset code is verified.
- **VerificationAttemptCounter** now also covers `password_reset` and refuses resends during a lockout.
- **ClientSession** is the in-memory auth state of each tab. It is listed so its states and sign-out reasons are explicit.
