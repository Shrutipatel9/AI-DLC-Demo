"""Retry policy with exponential backoff, jitter and a total time budget (NFR5.1, NFR5.3).

Shared by vendor adapters. Rules (reliability design section 2):

- at most ``max_attempts`` attempts (default 3 = 1 + 2 retries);
- delay before retry ``n`` = ``min(4 s, 0.5 s * 2**n) + random(0, 250 ms)``;
- each attempt's timeout = ``min(attempt_timeout, remaining budget)``;
- no attempt starts with less than ``min_attempt_seconds`` (2 s) left;
- only errors the caller marks as retryable are retried.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")

logger = logging.getLogger("platform.retry")


class Deadline:
    """A point in monotonic time by which work must finish.

    Args:
        seconds: Budget from now.
        monotonic: Injectable time source (``time.monotonic`` by default).
    """

    def __init__(self, seconds: float, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._monotonic = monotonic
        self._ends_at = monotonic() + seconds

    def remaining(self) -> float:
        """Seconds left (never negative)."""
        return max(0.0, self._ends_at - self._monotonic())

    def expired(self) -> bool:
        """True when no time is left."""
        return self.remaining() <= 0.0


class RetryBudgetExhausted(Exception):  # noqa: N818  (domain name reads better)
    """The budget ran out before an attempt could start. Wraps the last error, if any."""

    def __init__(self, last_error: BaseException | None) -> None:
        super().__init__("retry budget exhausted")
        self.last_error = last_error


@dataclass(frozen=True)
class RetryPolicy:
    """Backoff and budget rules for one outside call.

    Attributes:
        max_attempts: Total attempts including the first.
        attempt_timeout: Upper bound for one attempt, in seconds.
        min_attempt_seconds: Do not start an attempt with less time than this left.
        base_delay: First backoff delay before jitter.
        max_delay: Cap for the exponential delay.
        max_jitter: Upper bound of the random jitter added to each delay.
    """

    max_attempts: int = 3
    attempt_timeout: float = 10.0
    min_attempt_seconds: float = 2.0
    base_delay: float = 0.5
    max_delay: float = 4.0
    max_jitter: float = 0.25
    sleep: Callable[[float], None] = field(default=time.sleep, compare=False, repr=False)
    jitter: Callable[[float, float], float] = field(
        default=random.uniform,
        compare=False,
        repr=False,
    )

    def delay_for(self, retry_number: int) -> float:
        """Delay before retry ``retry_number`` (1-based), including jitter."""
        exponential = min(self.max_delay, self.base_delay * (2.0**retry_number))
        return exponential + self.jitter(0.0, self.max_jitter)

    def run(
        self,
        operation: Callable[[float, int], T],
        *,
        deadline: Deadline,
        is_retryable: Callable[[BaseException], bool],
        adapter: str,
    ) -> T:
        """Run ``operation(timeout, attempt)`` until it succeeds or the rules say stop.

        Args:
            operation: Called with the per-attempt timeout and the 1-based attempt number.
            deadline: The total budget.
            is_retryable: Classifies an error as transient (retry) or permanent (stop).
            adapter: Adapter name for the ``vendor.retry`` log line.

        Returns:
            The operation's result.

        Raises:
            RetryBudgetExhausted: When no attempt could start in time.
            Exception: The last error, when it is permanent or attempts ran out.
        """
        last_error: BaseException | None = None
        for attempt in range(1, self.max_attempts + 1):
            remaining = deadline.remaining()
            if remaining < self.min_attempt_seconds:
                raise RetryBudgetExhausted(last_error) from last_error
            timeout = min(self.attempt_timeout, remaining)
            try:
                return operation(timeout, attempt)
            except Exception as exc:
                last_error = exc
                if not is_retryable(exc) or attempt == self.max_attempts:
                    raise
                logger.warning(
                    "vendor call failed; retrying",
                    extra={
                        "event": "vendor.retry",
                        "adapter": adapter,
                        "errorClass": type(exc).__name__,
                        "attempt": attempt,
                    },
                )
                pause = min(self.delay_for(attempt), max(0.0, deadline.remaining()))
                if pause > 0:
                    self.sleep(pause)
        raise RetryBudgetExhausted(last_error)  # pragma: no cover  (loop always returns/raises)
