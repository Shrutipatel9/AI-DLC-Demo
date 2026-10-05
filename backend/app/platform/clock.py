"""Clock port (injectable time source).

Services never call ``datetime.now()`` directly. They take a :class:`Clock`, so tests
can freeze and advance time (code expiry, cooldowns, lockouts, token expiry) without
sleeping.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """Source of the current time. Always returns a timezone-aware UTC datetime."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        ...


class SystemClock:
    """The real wall clock."""

    def now(self) -> datetime:
        """Return the current UTC time from the operating system."""
        return datetime.now(UTC)


class FrozenClock:
    """A clock that only moves when told to. Used by tests.

    Args:
        start: The initial time. Must be timezone-aware.
    """

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            raise ValueError("FrozenClock needs a timezone-aware datetime")
        self._now = start.astimezone(UTC)

    def now(self) -> datetime:
        """Return the frozen time."""
        return self._now

    def advance(self, delta: timedelta | None = None, **kwargs: float) -> datetime:
        """Move the clock forward and return the new time.

        Args:
            delta: How far to move. Alternatively pass ``timedelta`` keyword arguments.
            **kwargs: Keyword arguments for :class:`datetime.timedelta`.
        """
        step = delta if delta is not None else timedelta(**kwargs)
        if step < timedelta(0):
            raise ValueError("FrozenClock cannot move backwards")
        self._now = self._now + step
        return self._now

    def set(self, moment: datetime) -> None:
        """Jump to a specific time (timezone-aware)."""
        if moment.tzinfo is None:
            raise ValueError("FrozenClock needs a timezone-aware datetime")
        self._now = moment.astimezone(UTC)
