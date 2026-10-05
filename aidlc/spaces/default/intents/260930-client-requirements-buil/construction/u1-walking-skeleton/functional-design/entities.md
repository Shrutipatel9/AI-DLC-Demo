# Entities — U1 Walking Skeleton

These are the entities this unit creates. All three are owned by the Identity component (`inception/domain-design/components.md`). `PasswordResetToken` and refresh-token rotation arrive in U2; the `RefreshSession` shape is defined in full here so U2 needs no schema rework. The model is technology-agnostic: logical types only.

```yaml
entities:
  - name: User
    description: A person with an account. Created unverified at sign-up step 1; verified by the emailed code.
    attributes:
      - { name: id, type: uuid, required: true, unique: true, default: generated }
      - { name: fullName, type: string, required: true, min: 1, max: 120, constraints: "trimmed; not editable after sign-up (FR13.1)" }
      - { name: email, type: string, required: true, unique: true, max: 254, constraints: "stored lower-cased and trimmed; uniqueness is case-insensitive" }
      - { name: passwordHash, type: string, required: true, constraints: "slow adaptive hash with per-hash salt; never the password (BR1.5)" }
      - { name: isVerified, type: boolean, required: true, default: false }
      - { name: role, type: enum, required: true, allowed: [user], default: user, constraints: "admin reserved for later (AUTH-009)" }
      - { name: createdAt, type: timestamp, required: true, default: now, constraints: "shown as member-since" }
      - { name: verifiedAt, type: timestamp, required: false }
      - { name: updatedAt, type: timestamp, required: true, default: now }
    constraints:
      - "verifiedAt is set if and only if isVerified is true"
    relationships:
      - { to: OneTimeCode, cardinality: "1 to many", direction: "User has codes" }
      - { to: RefreshSession, cardinality: "1 to many", direction: "User has sessions" }

  - name: OneTimeCode
    description: A 6-digit code emailed for sign-up or login (reset in U2). Only its hash is stored.
    attributes:
      - { name: id, type: uuid, required: true, unique: true, default: generated }
      - { name: userId, type: uuid, required: true, references: User.id }
      - { name: purpose, type: enum, required: true, allowed: [signup, login, password_reset] }
      - { name: codeHash, type: string, required: true, constraints: "keyed hash of the 6-digit code; the plain code is never stored or logged" }
      - { name: issuedAt, type: timestamp, required: true }
      - { name: expiresAt, type: timestamp, required: true, constraints: "issuedAt + configured lifetime (initially 10 minutes)" }
      - { name: consumedAt, type: timestamp, required: false, constraints: "set on successful verification; a consumed code never verifies again" }
      - { name: supersededAt, type: timestamp, required: false, constraints: "set when a newer code for the same user and purpose is issued" }
    constraints:
      - "At most one live code (not consumed, not superseded, not expired) per (userId, purpose)"
    relationships:
      - { to: User, cardinality: "many to 1", direction: "code belongs to user" }

  - name: VerificationAttemptCounter
    description: Failed-code counter per account and purpose, independent of individual codes so a resend cannot reset it (BR2.7). U1 counts attempts; U2 adds the user-visible lockout screens.
    attributes:
      - { name: userId, type: uuid, required: true, references: User.id }
      - { name: purpose, type: enum, required: true, allowed: [signup, login, password_reset] }
      - { name: failedCount, type: integer, required: true, default: 0, min: 0 }
      - { name: lockedUntil, type: timestamp, required: false }
      - { name: lastSentAt, type: timestamp, required: false, constraints: "drives the 60-second resend cooldown" }
    constraints:
      - "Primary identity is (userId, purpose)"

  - name: RefreshSession
    description: Server record of an issued refresh token. Stores only an identifier, never the raw token. U1 issues sessions; U2 adds rotation, reuse detection and revocation flows.
    attributes:
      - { name: tokenId, type: uuid, required: true, unique: true, constraints: "the cookie carries tokenId plus a secret; only a hash of the secret is stored" }
      - { name: secretHash, type: string, required: true }
      - { name: userId, type: uuid, required: true, references: User.id }
      - { name: familyId, type: uuid, required: true, constraints: "new family per sign-in" }
      - { name: parentTokenId, type: uuid, required: false, references: RefreshSession.tokenId }
      - { name: issuedAt, type: timestamp, required: true }
      - { name: expiresAt, type: timestamp, required: true, constraints: "issuedAt + configured lifetime (initially 7 days)" }
      - { name: rotatedAt, type: timestamp, required: false }
      - { name: revokedAt, type: timestamp, required: false }
    relationships:
      - { to: User, cardinality: "many to 1", direction: "session belongs to user" }
      - { to: RefreshSession, cardinality: "0..1 to 0..1", direction: "child rotated from parent (U2)" }
```

## Summary
- **User:** the account. Unverified until the emailed code is entered. The role is always `user` for now.
- **OneTimeCode:** a hashed 6-digit code per purpose. It expires, can be used once, and is replaced by a newer one.
- **VerificationAttemptCounter:** counts failed codes per account and purpose. It is separate from the codes so a resend can't reset it.
- **RefreshSession:** the server-side record of each refresh cookie, keyed by an identifier. It is ready for U2's rotation and reuse detection.

The access token is a short-lived signed token and is never stored, so it is not an entity.
