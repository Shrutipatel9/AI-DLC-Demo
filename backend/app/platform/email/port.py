"""Email sending port (contract C10 ``EmailSender``, NFR12.1, BR7.4).

Implementations are chosen by configuration (``EMAIL_BACKEND``):

- ``smtp`` -> :class:`app.platform.email.smtp.SmtpEmailSender` (Mailpit locally);
- ``fake`` -> :class:`app.platform.email.fake.RecordingEmailSender` (tests only).

Every send has a deadline, and every failure is a typed :class:`EmailError`.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Protocol

from app.platform.retry import Deadline


class EmailTemplate(StrEnum):
    """Templates available to senders (NFR12.2)."""

    SIGNUP_CODE = "signup_code"
    LOGIN_CODE = "login_code"
    PASSWORD_RESET_CODE = "password_reset_code"  # noqa: S105  (a template name, not a secret)


class EmailError(Exception):
    """Base class for email failures."""


class EmailTransientError(EmailError):
    """A failure worth retrying (connection error, SMTP 421/450/451/452)."""


class EmailTimeoutError(EmailTransientError):
    """The provider did not answer within the attempt timeout or the total budget."""


class EmailPermanentError(EmailError):
    """The provider rejected the message for good (for example SMTP 550/553)."""


class EmailSender(Protocol):
    """Sends one templated email."""

    def send(
        self,
        to: str,
        template: EmailTemplate,
        variables: Mapping[str, Any],
        *,
        deadline: Deadline,
    ) -> None:
        """Send the email or raise :class:`EmailError`. Blocking; call it from a thread."""
        ...
