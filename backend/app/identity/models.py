"""Identity ORM models (functional-design ``entities.md``).

Tables: ``users``, ``one_time_codes``, ``verification_attempts``, ``refresh_sessions``
(U1); ``password_reset_tokens`` and ``email_attempt_counters`` (U2, migration 0002).
These models never leave the identity module; other modules use ``identity.public``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


class CodePurpose(StrEnum):
    """What a one-time code is for (BR2.5: a code verifies only for its purpose)."""

    SIGNUP = "signup"
    LOGIN = "login"
    PASSWORD_RESET = "password_reset"  # noqa: S105  (a purpose name, not a secret)


class RevokedReason(StrEnum):
    """Why a refresh session was revoked (U2 ``entities.md``)."""

    LOGOUT = "logout"
    REUSE_DETECTED = "reuse_detected"
    PASSWORD_RESET = "password_reset"  # noqa: S105  (a reason name, not a secret)
    PASSWORD_CHANGED = "password_changed"  # noqa: S105  (a reason name, not a secret)


class Role(StrEnum):
    """User roles. Only ``user`` exists for now (AUTH-009 reserves admin for later)."""

    USER = "user"


_PURPOSES = "', '".join(p.value for p in CodePurpose)
_REASONS = "', '".join(r.value for r in RevokedReason)


class User(Base):
    """A person with an account; unverified until the emailed code is entered."""

    __tablename__ = "users"
    __table_args__ = (
        Index("uq_users_email_lower", func.lower(text("email")), unique=True),
        CheckConstraint("role IN ('user')", name="role_allowed"),
        CheckConstraint("(verified_at IS NOT NULL) = is_verified", name="verified_at_matches_flag"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str] = mapped_column(String(20), default=Role.USER.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OneTimeCode(Base):
    """A 6-digit emailed code. Only its keyed hash is stored (BR2.2)."""

    __tablename__ = "one_time_codes"
    __table_args__ = (
        CheckConstraint(f"purpose IN ('{_PURPOSES}')", name="purpose_allowed"),
        Index(
            "uq_one_time_codes_live",
            "user_id",
            "purpose",
            unique=True,
            postgresql_where=text("consumed_at IS NULL AND superseded_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    purpose: Mapped[str] = mapped_column(String(20))
    code_hash: Mapped[str] = mapped_column(String(64))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VerificationAttemptCounter(Base):
    """Failed-code counter per (user, purpose); separate so a resend cannot reset it."""

    __tablename__ = "verification_attempts"
    __table_args__ = (
        CheckConstraint(f"purpose IN ('{_PURPOSES}')", name="purpose_allowed"),
        CheckConstraint("failed_count >= 0", name="failed_count_non_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    purpose: Mapped[str] = mapped_column(String(20), primary_key=True)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: When the sign-up, login password step or reset request started the current flow;
    #: never moved by a resend. BR1.6's 10-minute windows are measured from it (U2 R-06).
    flow_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailAttemptCounter(Base):
    """Shadow counter for emails without a matching account (U2 FD post-review R-01).

    Keyed by ``HMAC(EMAIL_HASH_KEY, normalised email)``, so unknown emails lock after five
    wrong codes exactly like real accounts and the email itself is never stored.
    """

    __tablename__ = "email_attempt_counters"
    __table_args__ = (
        CheckConstraint(f"purpose IN ('{_PURPOSES}')", name="purpose_allowed"),
        CheckConstraint("failed_count >= 0", name="failed_count_non_negative"),
    )

    email_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(20), primary_key=True)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    flow_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PasswordResetToken(Base):
    """Single-use proof that a reset code was verified (BR4.3, NFR2.9). Hash only."""

    __tablename__ = "password_reset_tokens"

    reset_token_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshSession(Base):
    """Server record of an issued refresh cookie: its id and a hash of its secret only.

    U2 adds rotation (``rotated_at``, ``parent_token_id``), revocation with a reason and
    the SHA-256 of the per-call refresh attempt id (``attempt_hash``, NFR2.3).
    """

    __tablename__ = "refresh_sessions"
    __table_args__ = (
        CheckConstraint(
            f"revoked_reason IS NULL OR revoked_reason IN ('{_REASONS}')",
            name="revoked_reason_allowed",
        ),
        CheckConstraint(
            "(revoked_at IS NULL) = (revoked_reason IS NULL)", name="revoked_reason_with_time"
        ),
        Index(
            "ix_refresh_sessions_user_id_usable",
            "user_id",
            postgresql_where=text("revoked_at IS NULL AND rotated_at IS NULL"),
        ),
    )

    token_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    secret_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    parent_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("refresh_sessions.token_id", ondelete="SET NULL"),
        index=True,
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(20))
    attempt_hash: Mapped[str | None] = mapped_column(String(64))
