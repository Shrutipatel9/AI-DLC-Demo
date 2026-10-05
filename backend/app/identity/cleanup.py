"""Identity clean-up command (U2 NFR11.3; NFR design Q1, post-review R-10).

Run it any time; it is idempotent (a second run deletes nothing)::

    uv run python -m app.identity.cleanup

Until a host exists it is run by hand; a host scheduler will run it daily. It deletes, in
batches of 1,000 rows (``ORDER BY key LIMIT 1000 FOR UPDATE SKIP LOCKED``, so it never
waits on, or blocks, a live request):

- refresh sessions that expired, were rotated, or were revoked more than 30 days ago
  (``parent_token_id`` is ``ON DELETE SET NULL``, so a surviving child is unaffected);
- password-reset tokens used, or expired, more than 30 days ago;
- shadow counters (``email_attempt_counters``) idle for more than 1 day and not locked.

Each batch is its own short transaction.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import ColumnElement, Delete, delete, or_, select, tuple_
from sqlalchemy.orm import Session

from app.identity.models import EmailAttemptCounter, PasswordResetToken, RefreshSession
from app.platform.clock import Clock, SystemClock
from app.platform.db import SessionFactory, create_db_engine, create_session_factory
from app.platform.logging import configure_logging
from app.platform.settings import load_settings

logger = logging.getLogger("identity.cleanup")

BATCH_SIZE = 1000
HISTORY = timedelta(days=30)
SHADOW_IDLE = timedelta(days=1)


@dataclass(frozen=True)
class CleanupReport:
    """Rows deleted per table."""

    refresh_sessions: int
    password_reset_tokens: int
    email_attempt_counters: int


def _delete_in_batches(
    session_factory: SessionFactory, build: Callable[[], Delete], batch_size: int
) -> int:
    total = 0
    while True:
        with session_factory() as session:
            deleted = _run_batch(session, build())
            session.commit()
        total += deleted
        if deleted < batch_size:
            return total


def _run_batch(session: Session, statement: Delete) -> int:
    result = session.execute(statement)
    return int(getattr(result, "rowcount", 0) or 0)


def _sessions_batch(cutoff_expr: ColumnElement[bool], batch_size: int) -> Delete:
    victims = (
        select(RefreshSession.token_id)
        .where(cutoff_expr)
        .order_by(RefreshSession.token_id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    return delete(RefreshSession).where(RefreshSession.token_id.in_(victims))


def run_cleanup(
    session_factory: SessionFactory, clock: Clock, *, batch_size: int = BATCH_SIZE
) -> CleanupReport:
    """Delete old identity rows in batches and return how many were removed."""
    now = clock.now()
    old = now - HISTORY
    sessions_cutoff = or_(
        RefreshSession.expires_at < old,
        RefreshSession.rotated_at < old,
        RefreshSession.revoked_at < old,
    )
    tokens_cutoff = or_(PasswordResetToken.used_at < old, PasswordResetToken.expires_at < old)
    shadow_cutoff = (EmailAttemptCounter.updated_at < now - SHADOW_IDLE) & or_(
        EmailAttemptCounter.locked_until.is_(None), EmailAttemptCounter.locked_until <= now
    )

    def tokens_batch() -> Delete:
        victims = (
            select(PasswordResetToken.reset_token_id)
            .where(tokens_cutoff)
            .order_by(PasswordResetToken.reset_token_id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        return delete(PasswordResetToken).where(PasswordResetToken.reset_token_id.in_(victims))

    def shadow_batch() -> Delete:
        victims = (
            select(EmailAttemptCounter.email_hash, EmailAttemptCounter.purpose)
            .where(shadow_cutoff)
            .order_by(EmailAttemptCounter.email_hash, EmailAttemptCounter.purpose)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        return delete(EmailAttemptCounter).where(
            tuple_(EmailAttemptCounter.email_hash, EmailAttemptCounter.purpose).in_(victims)
        )

    report = CleanupReport(
        refresh_sessions=_delete_in_batches(
            session_factory, lambda: _sessions_batch(sessions_cutoff, batch_size), batch_size
        ),
        password_reset_tokens=_delete_in_batches(session_factory, tokens_batch, batch_size),
        email_attempt_counters=_delete_in_batches(session_factory, shadow_batch, batch_size),
    )
    logger.info(
        "identity clean-up finished",
        extra={
            "event": "auth.cleanup.finished",
            "count": report.refresh_sessions
            + report.password_reset_tokens
            + report.email_attempt_counters,
        },
    )
    return report


def main() -> int:
    """Command-line entry point: load settings, clean up, print a summary. Returns 0."""
    settings = load_settings()
    configure_logging(settings.log_level)
    engine = create_db_engine(settings)
    try:
        report = run_cleanup(create_session_factory(engine), SystemClock())
    finally:
        engine.dispose()
    print(  # command-line summary for the operator
        f"Deleted {report.refresh_sessions} refresh sessions, "
        f"{report.password_reset_tokens} reset tokens, "
        f"{report.email_attempt_counters} shadow counters."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
