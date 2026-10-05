"""Email port, adapters and dispatcher (contract C10, NFR12, NFR5.1-NFR5.3, NFR5.13)."""

from __future__ import annotations

from app.platform.email.fake import RecordingEmailSender
from app.platform.email.port import EmailSender
from app.platform.email.smtp import SmtpConfig, SmtpEmailSender
from app.platform.retry import RetryPolicy
from app.platform.settings import Settings


def build_email_sender(settings: Settings) -> EmailSender:
    """Choose the email adapter from ``EMAIL_BACKEND`` (AC1.6.1, BR7.4-BR7.6)."""
    if settings.email_backend == "fake":
        return RecordingEmailSender(settings.app_env)
    password = settings.smtp_password.get_secret_value() if settings.smtp_password else None
    config = SmtpConfig(
        host=settings.smtp_host,
        port=settings.smtp_port,
        sender=settings.email_from,
        username=settings.smtp_username or None,
        password=password or None,
        starttls=settings.smtp_starttls,
    )
    policy = RetryPolicy(
        max_attempts=settings.email_max_attempts,
        attempt_timeout=settings.email_attempt_timeout_seconds,
    )
    return SmtpEmailSender(config, policy)
