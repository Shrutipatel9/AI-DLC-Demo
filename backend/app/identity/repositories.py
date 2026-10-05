"""Identity data access (users, one-time codes, attempt counters, refresh sessions).

Repositories never commit; the calling service owns the transaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.identity.models import (
    CodePurpose,
    EmailAttemptCounter,
    OneTimeCode,
    PasswordResetToken,
    RefreshSession,
    RevokedReason,
    User,
    VerificationAttemptCounter,
)

# --- Attempt counters ------------------------------------------------------------------------


def lock_counter(
    session: Session, user_id: uuid.UUID, purpose: CodePurpose
) -> VerificationAttemptCounter:
    """Ensure the (user, purpose) counter row exists, then lock it ``FOR UPDATE``.

    ``INSERT ... ON CONFLICT DO NOTHING`` first, so two concurrent first calls cannot
    collide on the primary key, and the row always exists before it is locked
    (security design section 2).
    """
    session.execute(
        pg_insert(VerificationAttemptCounter)
        .values(user_id=user_id, purpose=purpose.value, failed_count=0)
        .on_conflict_do_nothing(index_elements=["user_id", "purpose"])
    )
    counter = session.scalars(
        select(VerificationAttemptCounter)
        .where(
            VerificationAttemptCounter.user_id == user_id,
            VerificationAttemptCounter.purpose == purpose.value,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
    return counter


def touch_email_counter(
    session: Session,
    email_hash: str,
    purpose: CodePurpose,
    now: datetime,
    *,
    start_flow: bool = False,
) -> None:
    """Upsert the shadow counter for (email hash, purpose); optionally start a flow (R-06)."""
    values: dict[str, object] = {"updated_at": now}
    if start_flow:
        values["flow_started_at"] = now
    session.execute(
        pg_insert(EmailAttemptCounter)
        .values(email_hash=email_hash, purpose=purpose.value, failed_count=0, **values)
        .on_conflict_do_update(index_elements=["email_hash", "purpose"], set_=values)
    )


def lock_email_counter(
    session: Session, email_hash: str, purpose: CodePurpose, now: datetime
) -> EmailAttemptCounter:
    """Ensure the shadow counter row exists, then lock it ``FOR UPDATE`` (same shape as U1)."""
    session.execute(
        pg_insert(EmailAttemptCounter)
        .values(email_hash=email_hash, purpose=purpose.value, failed_count=0, updated_at=now)
        .on_conflict_do_nothing(index_elements=["email_hash", "purpose"])
    )
    return session.scalars(
        select(EmailAttemptCounter)
        .where(
            EmailAttemptCounter.email_hash == email_hash,
            EmailAttemptCounter.purpose == purpose.value,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


# --- Password reset tokens -------------------------------------------------------------------


def invalidate_reset_tokens(session: Session, user_id: uuid.UUID, now: datetime) -> None:
    """Mark every unused reset token of the user as used (a newer one replaces them, BR4.3)."""
    session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )


def add_reset_token(
    session: Session,
    *,
    user_id: uuid.UUID,
    token_hash: str,
    issued_at: datetime,
    expires_at: datetime,
) -> PasswordResetToken:
    """Store a reset token (hash only)."""
    row = PasswordResetToken(
        reset_token_id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    session.add(row)
    session.flush()
    return row


def consume_reset_token(session: Session, token_hash: str, now: datetime) -> uuid.UUID | None:
    """Atomically use a valid token; returns its user id, or ``None`` (R-09).

    ``UPDATE ... WHERE used_at IS NULL AND expires_at > now RETURNING user_id``: two
    concurrent resets with one token serialise on the row, and the second sees ``used_at``
    set and matches no row.
    """
    return session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(PasswordResetToken.user_id)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()


# --- One-time codes --------------------------------------------------------------------------


def live_code(session: Session, user_id: uuid.UUID, purpose: CodePurpose) -> OneTimeCode | None:
    """The code for (user, purpose) that is neither consumed nor superseded (may be expired)."""
    return session.scalars(
        select(OneTimeCode)
        .where(
            OneTimeCode.user_id == user_id,
            OneTimeCode.purpose == purpose.value,
            OneTimeCode.consumed_at.is_(None),
            OneTimeCode.superseded_at.is_(None),
        )
        .execution_options(populate_existing=True)
    ).first()


def supersede_live_codes(
    session: Session, user_id: uuid.UUID, purpose: CodePurpose, now: datetime
) -> None:
    """Mark every live code for (user, purpose) as superseded."""
    session.execute(
        update(OneTimeCode)
        .where(
            OneTimeCode.user_id == user_id,
            OneTimeCode.purpose == purpose.value,
            OneTimeCode.consumed_at.is_(None),
            OneTimeCode.superseded_at.is_(None),
        )
        .values(superseded_at=now)
        .execution_options(synchronize_session="evaluate")
    )


def supersede_code(session: Session, code_id: uuid.UUID, now: datetime) -> None:
    """Mark one unused code superseded (email-failure compensation; never a newer code)."""
    session.execute(
        update(OneTimeCode)
        .where(
            OneTimeCode.id == code_id,
            OneTimeCode.superseded_at.is_(None),
            OneTimeCode.consumed_at.is_(None),
        )
        .values(superseded_at=now)
        .execution_options(synchronize_session="evaluate")
    )


def add_code(
    session: Session,
    *,
    user_id: uuid.UUID,
    purpose: CodePurpose,
    code_hash: str,
    issued_at: datetime,
    expires_at: datetime,
) -> OneTimeCode:
    """Insert a new code row (hash only)."""
    row = OneTimeCode(
        id=uuid.uuid4(),
        user_id=user_id,
        purpose=purpose.value,
        code_hash=code_hash,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    session.add(row)
    session.flush()
    return row


def consume_code(session: Session, code_id: uuid.UUID, now: datetime) -> bool:
    """Set ``consumed_at`` only if still unconsumed. Returns True when this call consumed it."""
    result = session.execute(
        update(OneTimeCode)
        .where(OneTimeCode.id == code_id, OneTimeCode.consumed_at.is_(None))
        .values(consumed_at=now)
        .execution_options(synchronize_session="evaluate")
    )
    return int(getattr(result, "rowcount", 0) or 0) == 1


# --- Users -----------------------------------------------------------------------------------


def find_user_by_email(session: Session, email: str, *, for_update: bool = False) -> User | None:
    """Find a user by normalised email (case-insensitive)."""
    statement = select(User).where(func.lower(User.email) == email.strip().lower())
    if for_update:
        statement = statement.with_for_update()
    return session.scalars(statement).first()


def get_user(session: Session, user_id: uuid.UUID, *, for_update: bool = False) -> User | None:
    """Load a user by id (optionally locked ``FOR UPDATE``)."""
    if for_update:
        return session.get(User, user_id, with_for_update=True, populate_existing=True)
    return session.get(User, user_id)


def add_user(
    session: Session, *, full_name: str, email: str, password_hash: str, now: datetime
) -> User:
    """Insert a new unverified user with role ``user`` (BR1.6)."""
    user = User(
        id=uuid.uuid4(),
        full_name=full_name,
        email=email,
        password_hash=password_hash,
        is_verified=False,
        role="user",
        created_at=now,
        updated_at=now,
        verified_at=None,
    )
    session.add(user)
    session.flush()
    return user


# --- Refresh sessions ------------------------------------------------------------------------


def add_refresh_session(
    session: Session,
    *,
    token_id: uuid.UUID,
    secret_hash: str,
    user_id: uuid.UUID,
    family_id: uuid.UUID,
    issued_at: datetime,
    expires_at: datetime,
    parent_token_id: uuid.UUID | None = None,
    attempt_hash: str | None = None,
) -> RefreshSession:
    """Store a refresh session (identifier and secret hash only)."""
    row = RefreshSession(
        token_id=token_id,
        secret_hash=secret_hash,
        user_id=user_id,
        family_id=family_id,
        parent_token_id=parent_token_id,
        issued_at=issued_at,
        expires_at=expires_at,
        attempt_hash=attempt_hash,
    )
    session.add(row)
    session.flush()
    return row


def get_refresh_session(
    session: Session, token_id: uuid.UUID, *, for_update: bool = False
) -> RefreshSession | None:
    """Load one refresh session, optionally locked ``FOR UPDATE`` (always fresh from the DB)."""
    statement = (
        select(RefreshSession)
        .where(RefreshSession.token_id == token_id)
        .execution_options(populate_existing=True)
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalars(statement).first()


def lock_child_session(session: Session, parent_token_id: uuid.UUID) -> RefreshSession | None:
    """Lock the session created by rotating ``parent_token_id`` (parent first, then child)."""
    return session.scalars(
        select(RefreshSession)
        .where(RefreshSession.parent_token_id == parent_token_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()


def refresh_revoked_at(session: Session, token_id: uuid.UUID) -> datetime | None:
    """Re-read ``revoked_at`` of one session (re-check after inserting a child, R-01)."""
    return session.scalars(
        select(RefreshSession.revoked_at).where(RefreshSession.token_id == token_id)
    ).first()


def _scope(
    *,
    family_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    exclude_family: uuid.UUID | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if family_id is not None:
        conditions.append(RefreshSession.family_id == family_id)
    if user_id is not None:
        conditions.append(RefreshSession.user_id == user_id)
    if exclude_family is not None:
        conditions.append(RefreshSession.family_id != exclude_family)
    if not conditions:
        raise ValueError("a revocation needs a family or a user scope")
    return conditions


def revoke_sessions(
    session: Session,
    *,
    reason: RevokedReason,
    now: datetime,
    family_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    exclude_family: uuid.UUID | None = None,
) -> int:
    """Lock-then-update revocation (U2 NFD post-review R-01). Returns usable sessions revoked.

    1. ``SELECT ... FOR UPDATE`` the usable sessions in scope, ordered by ``token_id``. This
       waits for any in-flight refresh holding a row lock in the scope.
    2. A separate ``UPDATE`` (a new statement, so a new snapshot that sees a child the
       waited-for refresh committed) revokes every not-yet-revoked session in scope.
    """
    scope = _scope(family_id=family_id, user_id=user_id, exclude_family=exclude_family)
    usable = and_(RefreshSession.revoked_at.is_(None), RefreshSession.rotated_at.is_(None))
    session.execute(
        select(RefreshSession.token_id)
        .where(*scope, usable)
        .order_by(RefreshSession.token_id)
        .with_for_update()
    ).all()
    result = session.execute(
        update(RefreshSession)
        .where(*scope, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=now, revoked_reason=reason.value)
        .returning(RefreshSession.rotated_at, RefreshSession.expires_at)
        .execution_options(synchronize_session=False)
    ).all()
    return sum(1 for rotated_at, expires_at in result if rotated_at is None and now < expires_at)
