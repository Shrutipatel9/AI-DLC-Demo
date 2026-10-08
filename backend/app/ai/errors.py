"""Typed vendor errors (AC1.12.2): a vendor failure is raised, never swallowed.

Messages never carry request or response bodies, so a photo or an answer cannot reach a log
through an error.
"""

from __future__ import annotations


class AiError(Exception):
    """Base class of every AI vendor failure."""

    def __init__(self, message: str = "The AI service failed.") -> None:
        super().__init__(message)
        self.message = message


class AiRateLimitError(AiError):
    """The vendor answered 429. ``retry_after`` is its hint in seconds, when it gave one."""

    def __init__(
        self,
        message: str = "The AI service is rate limiting us.",
        *,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AiTimeoutError(AiError):
    """The vendor did not answer within the adapter's timeout."""


class AiUnavailableError(AiError):
    """The vendor was unreachable or answered with a server error."""


class AiRequestRejectedError(AiError):
    """The vendor refused the request (a 4xx other than 429): retrying will not help."""


class AiBadOutputError(AiError):
    """The vendor answered, but the answer is not usable (not JSON, wrong shape)."""
