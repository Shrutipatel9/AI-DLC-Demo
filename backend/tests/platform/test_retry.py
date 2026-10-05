"""Retry policy and budget (NFR5.1, NFR5.3)."""

from __future__ import annotations

import pytest

from app.platform.retry import Deadline, RetryBudgetExhausted, RetryPolicy


class FakeTime:
    """Monotonic time that only moves when sleep() is called."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class TransientError(Exception):
    pass


class PermanentError(Exception):
    pass


def _policy(clock: FakeTime, **kwargs: float) -> RetryPolicy:
    return RetryPolicy(sleep=clock.sleep, jitter=lambda _a, _b: 0.1, **kwargs)  # type: ignore[arg-type]


def test_success_on_first_attempt_uses_capped_timeout() -> None:
    clock = FakeTime()
    seen: list[tuple[float, int]] = []
    result = _policy(clock).run(
        lambda timeout, attempt: seen.append((timeout, attempt)) or "ok",
        deadline=Deadline(25, clock.monotonic),
        is_retryable=lambda exc: isinstance(exc, TransientError),
        adapter="test",
    )
    assert result == "ok"
    assert seen == [(10.0, 1)]
    assert clock.sleeps == []


def test_transient_failures_are_retried_with_backoff() -> None:
    clock = FakeTime()
    calls: list[int] = []

    def operation(_timeout: float, attempt: int) -> str:
        calls.append(attempt)
        if attempt < 3:
            raise TransientError
        return "sent"

    result = _policy(clock).run(
        operation,
        deadline=Deadline(25, clock.monotonic),
        is_retryable=lambda exc: isinstance(exc, TransientError),
        adapter="test",
    )
    assert result == "sent"
    assert calls == [1, 2, 3]
    assert clock.sleeps == [pytest.approx(1.1), pytest.approx(2.1)]


def test_permanent_failure_is_not_retried() -> None:
    clock = FakeTime()
    calls: list[int] = []

    def operation(_timeout: float, attempt: int) -> None:
        calls.append(attempt)
        raise PermanentError

    with pytest.raises(PermanentError):
        _policy(clock).run(
            operation,
            deadline=Deadline(25, clock.monotonic),
            is_retryable=lambda exc: isinstance(exc, TransientError),
            adapter="test",
        )
    assert calls == [1]


def test_attempts_are_capped_and_last_error_raised() -> None:
    clock = FakeTime()
    calls: list[int] = []

    def operation(_timeout: float, attempt: int) -> None:
        calls.append(attempt)
        raise TransientError

    with pytest.raises(TransientError):
        _policy(clock).run(
            operation,
            deadline=Deadline(25, clock.monotonic),
            is_retryable=lambda exc: isinstance(exc, TransientError),
            adapter="test",
        )
    assert calls == [1, 2, 3]


def test_no_attempt_starts_with_less_than_two_seconds_left() -> None:
    clock = FakeTime()
    timeouts: list[float] = []

    def operation(timeout: float, _attempt: int) -> None:
        timeouts.append(timeout)
        clock.now += timeout  # the attempt used its whole timeout
        raise TransientError

    with pytest.raises(RetryBudgetExhausted) as caught:
        _policy(clock).run(
            operation,
            deadline=Deadline(12, clock.monotonic),
            is_retryable=lambda exc: isinstance(exc, TransientError),
            adapter="test",
        )
    # attempt 1: 10 s, sleep 1.1 s -> 0.9 s left, below the 2 s floor.
    assert timeouts == [10.0]
    assert isinstance(caught.value.last_error, TransientError)


def test_per_attempt_timeout_shrinks_to_remaining_budget() -> None:
    clock = FakeTime()
    timeouts: list[float] = []

    def operation(timeout: float, attempt: int) -> str:
        timeouts.append(timeout)
        clock.now += 9.0
        if attempt == 1:
            raise TransientError
        return "ok"

    _policy(clock).run(
        operation,
        deadline=Deadline(15, clock.monotonic),
        is_retryable=lambda exc: isinstance(exc, TransientError),
        adapter="test",
    )
    assert timeouts[0] == 10.0
    assert timeouts[1] == pytest.approx(15 - 9 - 1.1)


def test_deadline_reports_remaining_and_expiry() -> None:
    clock = FakeTime()
    deadline = Deadline(5, clock.monotonic)
    assert deadline.remaining() == 5
    clock.now = 6
    assert deadline.remaining() == 0
    assert deadline.expired()
