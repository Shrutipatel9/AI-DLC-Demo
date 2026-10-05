"""Recording email fake for tests (BR7.5, AC1.6.3).

It records every send so the test harness can read the code it carried. It can never
be enabled by production configuration: constructing it outside ``development`` or
``test`` raises. Codes are recorded in memory only and never logged.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.platform.email.port import EmailError, EmailTemplate, EmailTimeoutError
from app.platform.retry import Deadline

ALLOWED_ENVIRONMENTS = frozenset({"development", "test"})


class FakeNotAllowedError(RuntimeError):
    """The recording fake was requested in a non-test environment."""


@dataclass(frozen=True)
class SentEmail:
    """One recorded send."""

    to: str
    template: EmailTemplate
    variables: Mapping[str, Any]
    sent_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class RecordingEmailSender:
    """Email sender that records instead of sending.

    Args:
        app_env: The running environment; anything but development/test is refused.
        delay_seconds: Optional artificial latency (for bulkhead tests). It respects
            the deadline: when the delay outlasts it, a timeout error is raised.
        fail_with: Optional error to raise on every send (for failure-path tests).
    """

    adapter_name = "fake"

    def __init__(
        self,
        app_env: str = "test",
        *,
        delay_seconds: float = 0.0,
        fail_with: EmailError | None = None,
    ) -> None:
        if app_env not in ALLOWED_ENVIRONMENTS:
            raise FakeNotAllowedError("The recording email fake is only allowed in tests")
        self.delay_seconds = delay_seconds
        self.fail_with = fail_with
        self._sent: list[SentEmail] = []
        self._lock = threading.Lock()

    def send(
        self,
        to: str,
        template: EmailTemplate,
        variables: Mapping[str, Any],
        *,
        deadline: Deadline,
    ) -> None:
        """Record the email (after the optional delay or failure)."""
        if self.delay_seconds:
            wait = min(self.delay_seconds, deadline.remaining())
            time.sleep(wait)
            if wait < self.delay_seconds:
                raise EmailTimeoutError("fake send outlasted its deadline")
        if self.fail_with is not None:
            raise self.fail_with
        with self._lock:
            self._sent.append(SentEmail(to=to, template=template, variables=dict(variables)))

    @property
    def sent(self) -> list[SentEmail]:
        """All recorded emails, oldest first."""
        with self._lock:
            return list(self._sent)

    def last_code_for(self, email: str) -> str:
        """Return the code in the newest email sent to ``email``.

        Raises:
            LookupError: If nothing was sent to that address.
        """
        for message in reversed(self.sent):
            if message.to == email:
                return str(message.variables["code"])
        raise LookupError("no email recorded for that address")

    def clear(self) -> None:
        """Forget every recorded email."""
        with self._lock:
            self._sent.clear()
