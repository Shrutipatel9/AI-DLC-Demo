"""Request and response models for the auth API (contract C1; camelCase JSON)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel
from pydantic_core import PydanticCustomError

from app.identity.passwords import PasswordPolicy

_EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s.]{2,}$")
_policy = PasswordPolicy()


def normalise_email(value: str) -> str:
    """Trim and lower-case an email, then check its shape (BR1.1).

    Raises:
        PydanticCustomError: ``INVALID_EMAIL`` when the shape is wrong.
    """
    email = value.strip().lower()
    if len(email) > 254 or not _EMAIL_PATTERN.fullmatch(email) or ".." in email:
        raise PydanticCustomError("INVALID_EMAIL", "Enter a valid email address.")
    return email


def check_password_rule(value: str) -> str:
    """Apply the password rule (BR1.2) and name the failed parts.

    Raises:
        PydanticCustomError: ``PASSWORD_TOO_WEAK`` with the failed rules (never the value).
    """
    violations = _policy.violations(value)
    if violations:
        raise PydanticCustomError(
            "PASSWORD_TOO_WEAK",
            "The password does not meet the rule: {rules}.",
            {"rules": ", ".join(rule.value for rule in violations)},
        )
    return value


def normalise_name(value: str) -> str:
    """Collapse whitespace and require 1-120 characters (BR1.1).

    Raises:
        PydanticCustomError: ``INVALID_NAME`` when empty or too long.
    """
    name = " ".join(value.split())
    if not name or len(name) > 120:
        raise PydanticCustomError("INVALID_NAME", "Enter your full name (1-120 characters).")
    return name


Email = Annotated[str, StringConstraints(max_length=320), AfterValidator(normalise_email)]
FullName = Annotated[str, StringConstraints(max_length=1000), AfterValidator(normalise_name)]
NewPassword = Annotated[
    str, StringConstraints(max_length=1024), AfterValidator(check_password_rule)
]


class CamelModel(BaseModel):
    """Base model: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class RegisterRequest(CamelModel):
    """``POST /auth/register`` body."""

    full_name: FullName
    email: Email
    password: NewPassword


class LoginRequest(CamelModel):
    """``POST /auth/login`` body."""

    email: Email
    password: Annotated[str, StringConstraints(min_length=1, max_length=1024)]


class VerifyRequest(CamelModel):
    """``POST /auth/verify`` body."""

    email: Email
    code: Annotated[str, StringConstraints(pattern=r"^[0-9]{6}$")]
    purpose: Literal["signup", "login"]


class CodeSentResponse(CamelModel):
    """202 response after a code was emailed (no token, no cookie; BR1.7)."""

    masked_email: str = Field(examples=["m•••@example.com"])
    resend_available_at: datetime
    expires_at: datetime


class UserResponse(CamelModel):
    """The signed-in user (BR4.4)."""

    id: uuid.UUID
    full_name: str
    email: str
    is_verified: bool
    role: Literal["user"]
    member_since: datetime


class SessionResponse(CamelModel):
    """200 response from ``/auth/verify``; the refresh token travels only in the cookie."""

    access_token: str
    expires_at: datetime
    user: UserResponse


# --- U2 session security (contract C1) ------------------------------------------------------


class ResendRequest(CamelModel):
    """``POST /auth/resend-code`` body."""

    email: Email
    purpose: Literal["signup", "login", "password_reset"]


class ForgotPasswordRequest(CamelModel):
    """``POST /auth/password/forgot`` body."""

    email: Email


class ResetCodeVerifyRequest(CamelModel):
    """``POST /auth/password/verify-code`` body."""

    email: Email
    code: Annotated[str, StringConstraints(pattern=r"^[0-9]{6}$")]


class ResetPasswordRequest(CamelModel):
    """``POST /auth/password/reset`` body. The reset token is never a Bearer token."""

    reset_token: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    new_password: NewPassword


class ChangePasswordRequest(CamelModel):
    """``POST /auth/change-password`` body (the confirm field exists only in the form)."""

    current_password: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    new_password: NewPassword


class AccessTokenResponse(CamelModel):
    """200 from ``/auth/refresh``: a new access token; the refresh token is only a cookie."""

    access_token: str
    expires_at: datetime


class ResetTokenResponse(CamelModel):
    """200 from ``/auth/password/verify-code``: a single-use reset token."""

    reset_token: str
    expires_at: datetime
