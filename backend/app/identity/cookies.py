"""Refresh-token cookie (BR4.2, NFR2.7; AUTH-010, FE-002).

The cookie value is ``{token_id}.{base64url(secret)}`` with a 32-byte random secret.
The database stores the token id and ``sha256(secret)`` only, never the raw token.
Attributes come from settings: ``HttpOnly``, ``Max-Age`` (7 days), ``Path=/auth``,
``SameSite=Lax`` and ``Secure`` outside development/test.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from typing import Literal, TypedDict

from app.platform.settings import Settings

SECRET_BYTES = 32


def hash_secret(secret: bytes) -> str:
    """SHA-256 of the cookie secret, hex-encoded (what the database stores)."""
    return hashlib.sha256(secret).hexdigest()


@dataclass(frozen=True)
class RefreshToken:
    """A newly minted refresh token. ``value`` goes in the cookie only."""

    token_id: uuid.UUID
    secret: bytes = field(repr=False)

    @property
    def value(self) -> str:
        """The cookie value ``{token_id}.{base64url(secret)}``."""
        encoded = base64.urlsafe_b64encode(self.secret).rstrip(b"=").decode()
        return f"{self.token_id}.{encoded}"

    @property
    def secret_hash(self) -> str:
        """The value to store in ``refresh_sessions.secret_hash``."""
        return hash_secret(self.secret)


def new_refresh_token() -> RefreshToken:
    """Mint a refresh token with a random id and 32-byte secret."""
    return RefreshToken(token_id=uuid.uuid4(), secret=secrets.token_bytes(SECRET_BYTES))


def reissue_refresh_token(token_id: uuid.UUID) -> RefreshToken:
    """Mint a new secret for an existing token id (lost-response recovery, NFR2.3)."""
    return RefreshToken(token_id=token_id, secret=secrets.token_bytes(SECRET_BYTES))


def parse_refresh_cookie(value: str | None) -> RefreshToken | None:
    """Parse ``{token_id}.{base64url(secret)}``; ``None`` for anything malformed (BR2.4).

    Only the shape is checked here; the secret is compared with the stored hash by the
    session service, in constant time.
    """
    if not value or value.count(".") != 1:
        return None
    raw_id, raw_secret = value.split(".", 1)
    try:
        token_id = uuid.UUID(raw_id)
        padded = raw_secret + "=" * (-len(raw_secret) % 4)
        secret = base64.b64decode(padded, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error):
        return None
    if len(secret) != SECRET_BYTES:
        return None
    return RefreshToken(token_id=token_id, secret=secret)


class CookieParams(TypedDict):
    """Keyword arguments for ``Response.set_cookie``."""

    key: str
    max_age: int
    path: str
    domain: str | None
    secure: bool
    httponly: bool
    samesite: Literal["lax", "strict", "none"]


class ClearCookieParams(TypedDict):
    """Keyword arguments for ``Response.delete_cookie`` (same scope as the set cookie)."""

    key: str
    path: str
    domain: str | None
    secure: bool
    httponly: bool
    samesite: Literal["lax", "strict", "none"]


def clear_cookie_params(settings: Settings) -> ClearCookieParams:
    """Attributes that clear the refresh cookie (``Max-Age=0``, BR2.8)."""
    return ClearCookieParams(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,
    )


def refresh_cookie_params(settings: Settings) -> CookieParams:
    """Cookie attributes from configuration."""
    return CookieParams(
        key=settings.refresh_cookie_name,
        max_age=settings.refresh_token_ttl_seconds,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,
    )
