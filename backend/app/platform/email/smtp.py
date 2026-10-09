"""SMTP email adapter with a hard 25-second deadline (reliability design section 2).

Socket timeouts apply per blocking call, not to the whole send, so the deadline is
enforced three ways:

1. per-attempt socket timeout ``min(10 s, remaining)``;
2. before each SMTP command (connect, EHLO, STARTTLS, AUTH, MAIL, RCPT, DATA) the
   remaining budget is checked, and the attempt aborts with less than 1 s left;
3. a watchdog timer shuts the socket down at the deadline, so any pending call fails
   at once.

Retries follow :class:`app.platform.retry.RetryPolicy`.
"""

from __future__ import annotations

import email.policy
import logging
import smtplib
import socket
import ssl
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

from app.platform.email.port import (
    EmailPermanentError,
    EmailTemplate,
    EmailTimeoutError,
    EmailTransientError,
)
from app.platform.email.rendering import render_email
from app.platform.retry import Deadline, RetryBudgetExhausted, RetryPolicy

logger = logging.getLogger("platform.email.smtp")

TRANSIENT_SMTP_CODES = frozenset({421, 450, 451, 452})
MIN_SECONDS_PER_COMMAND = 1.0


@dataclass(frozen=True)
class SmtpConfig:
    """Connection settings for one SMTP server."""

    host: str
    port: int
    sender: str
    username: str | None = None
    password: str | None = None
    starttls: bool = False


class _Watchdog:
    """Shuts an SMTP socket down when the deadline passes."""

    def __init__(self, client: smtplib.SMTP, seconds: float) -> None:
        self.fired = False
        self._client = client
        self._timer = threading.Timer(max(0.0, seconds), self._fire)
        self._timer.daemon = True

    def _fire(self) -> None:
        self.fired = True
        sock = getattr(self._client, "sock", None)
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                logger.debug("watchdog: socket already closed")

    def __enter__(self) -> _Watchdog:
        self._timer.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._timer.cancel()


def classify_smtp_error(exc: BaseException) -> type[Exception]:
    """Return the email error class for an ``smtplib`` failure."""
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes = [code for code, _ in exc.recipients.values()]
        if codes and all(code in TRANSIENT_SMTP_CODES or 400 <= code < 500 for code in codes):
            return EmailTransientError
        return EmailPermanentError
    if isinstance(exc, smtplib.SMTPResponseException):
        if exc.smtp_code in TRANSIENT_SMTP_CODES or 400 <= exc.smtp_code < 500:
            return EmailTransientError
        return EmailPermanentError
    if isinstance(exc, TimeoutError | socket.timeout):
        return EmailTimeoutError
    return EmailTransientError


class SmtpEmailSender:
    """Sends templated email over SMTP within a deadline."""

    adapter_name = "smtp"

    def __init__(self, config: SmtpConfig, policy: RetryPolicy | None = None) -> None:
        self._config = config
        self._policy = policy or RetryPolicy()

    def send(
        self,
        to: str,
        template: EmailTemplate,
        variables: Mapping[str, Any],
        *,
        deadline: Deadline,
    ) -> None:
        """Render and send one email, retrying transient failures within ``deadline``.

        Raises:
            EmailTimeoutError: The budget ran out.
            EmailTransientError: Transient failures used up every attempt.
            EmailPermanentError: The server rejected the message.
        """
        message = self._build_message(to, template, variables)
        try:
            self._policy.run(
                lambda timeout, _attempt: self._attempt(message, to, timeout, deadline),
                deadline=deadline,
                is_retryable=lambda exc: isinstance(exc, EmailTransientError),
                adapter=self.adapter_name,
            )
        except RetryBudgetExhausted as exc:
            raise EmailTimeoutError("email send budget exhausted") from exc

    def _build_message(
        self, to: str, template: EmailTemplate, variables: Mapping[str, Any]
    ) -> EmailMessage:
        rendered = render_email(template, variables)
        message = EmailMessage()
        message["From"] = self._config.sender
        message["To"] = to
        message["Subject"] = rendered.subject
        message.set_content(rendered.text)
        message.add_alternative(rendered.html, subtype="html")
        return message

    @staticmethod
    def _check(deadline: Deadline) -> None:
        if deadline.remaining() < MIN_SECONDS_PER_COMMAND:
            raise EmailTimeoutError("not enough time left for the next SMTP command")

    def _attempt(self, message: EmailMessage, to: str, timeout: float, deadline: Deadline) -> None:
        client = smtplib.SMTP(timeout=timeout)
        with _Watchdog(client, deadline.remaining()) as watchdog:
            try:
                self._converse(client, message, to, deadline)
            except (EmailTimeoutError, EmailTransientError, EmailPermanentError):
                raise
            except (smtplib.SMTPException, OSError) as exc:
                if watchdog.fired:
                    raise EmailTimeoutError("email send deadline reached") from exc
                error_class = classify_smtp_error(exc)
                raise error_class(f"SMTP failure ({type(exc).__name__})") from exc
            finally:
                # close() never waits on the server, so a stalled server cannot
                # stretch the attempt past its deadline.
                client.close()

    def _converse(
        self, client: smtplib.SMTP, message: EmailMessage, to: str, deadline: Deadline
    ) -> None:
        config = self._config
        self._check(deadline)
        client.connect(config.host, config.port)
        # smtplib only records the host when it is passed to the constructor, and
        # starttls() needs it to verify the server certificate (server_hostname).
        client._host = config.host  # type: ignore[attr-defined]
        self._check(deadline)
        client.ehlo()
        if config.starttls:
            self._check(deadline)
            client.starttls(context=ssl.create_default_context())
            self._check(deadline)
            client.ehlo()
        if config.username:
            self._check(deadline)
            client.login(config.username, config.password or "")
        self._check(deadline)
        code, reply = client.mail(config.sender)
        if code != 250:
            raise smtplib.SMTPSenderRefused(code, reply, config.sender)
        self._check(deadline)
        code, reply = client.rcpt(to)
        if code not in (250, 251):
            raise smtplib.SMTPRecipientsRefused({to: (code, reply)})
        self._check(deadline)
        code, reply = client.data(message.as_bytes(policy=email.policy.SMTP))
        if code != 250:
            # smtplib returns the final DATA reply without raising; never treat a
            # rejection as a successful send.
            raise smtplib.SMTPDataError(code, reply)
        try:
            client.quit()
        except (smtplib.SMTPException, OSError):
            logger.debug("SMTP QUIT failed after a successful send")
