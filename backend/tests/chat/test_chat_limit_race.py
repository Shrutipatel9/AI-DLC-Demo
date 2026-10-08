"""AC10.3.3: with 49 used and two sends at once, the database grants exactly one."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.chat import repositories
from app.chat.models import ChatUsage
from tests.identity.conftest import TwoSessions, run_in_threads, two_sessions  # noqa: F401

DAY = date(2026, 10, 1)


def test_two_simultaneous_sends_at_49_of_50_accept_exactly_one(
    committed_session_factory: Callable[[], Session],
    two_sessions: TwoSessions,  # noqa: F811
) -> None:
    user_id = two_sessions.make_user()
    with committed_session_factory() as session:
        session.add(ChatUsage(user_id=user_id, day=DAY, used=49))
        session.commit()

    def attempt() -> bool:
        with committed_session_factory() as session:
            granted = repositories.reserve(session, user_id, DAY, 50)
            session.commit()
            return granted

    results = run_in_threads(attempt, attempt)

    assert sorted(results) == [False, True]
    with committed_session_factory() as session:
        assert repositories.used_today(session, user_id, DAY) == 50
        session.execute(delete(ChatUsage).where(ChatUsage.user_id == user_id))
        session.commit()


def test_the_first_message_of_a_day_creates_the_counter_and_release_never_goes_negative(
    committed_session_factory: Callable[[], Session],
    two_sessions: TwoSessions,  # noqa: F811
) -> None:
    user_id = two_sessions.make_user()
    with committed_session_factory() as session:
        assert repositories.reserve(session, user_id, DAY, 1) is True
        assert repositories.reserve(session, user_id, DAY, 1) is False
        repositories.release(session, user_id, DAY)
        repositories.release(session, user_id, DAY)
        session.commit()
        assert repositories.used_today(session, user_id, DAY) == 0
        session.execute(delete(ChatUsage).where(ChatUsage.user_id == user_id))
        session.commit()
