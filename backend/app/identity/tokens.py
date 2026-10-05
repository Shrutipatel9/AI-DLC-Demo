"""JWT access-token service (BR4.1, BR4.3, NFR2.6; AUTH-010-AUTH-012).

- HS256 only. The header ``alg`` must be ``HS256``; ``none`` and every other algorithm
  are refused before any key is touched.
- Claims: ``sub`` (user id), ``role``, ``iat``, ``exp`` (``iat`` + 15 minutes),
  ``typ="access"`` and a unique ``jti``.
- The header ``kid`` selects the key from ``JWT_SIGNING_KEYS``; ``JWT_ACTIVE_KID`` signs.
  During rotation both keys verify.
- Expiry is checked against the injected clock: a token is invalid when ``now >= exp``.
- Every key must be at least 32 bytes, and the active kid must exist, or construction
  (and therefore start-up) fails.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.platform.clock import Clock
from app.platform.settings import MIN_KEY_BYTES, Settings

ALGORITHM = "HS256"
ACCESS_TYPE = "access"
REQUIRED_CLAIMS = ("sub", "role", "iat", "exp", "typ", "jti")


class TokenConfigError(ValueError):
    """Signing configuration is unsafe (short key, unknown active kid, no keys)."""


class InvalidTokenError(Exception):
    """A presented token is missing, malformed, tampered, expired or of the wrong type."""


@dataclass(frozen=True)
class IssuedToken:
    """A signed access token and its expiry."""

    token: str
    expires_at: datetime
    jti: str


@dataclass(frozen=True)
class AccessClaims:
    """The verified claims of an access token."""

    user_id: uuid.UUID
    role: str
    jti: str
    issued_at: datetime
    expires_at: datetime


class TokenService:
    """Issues and verifies access tokens.

    Args:
        keys: ``kid`` -> key bytes (each at least 32 bytes).
        active_kid: The kid used to sign new tokens.
        clock: Time source (frozen in tests).
        access_ttl: Access-token lifetime (15 minutes by default).

    Raises:
        TokenConfigError: On an unsafe key configuration.
    """

    def __init__(
        self,
        *,
        keys: Mapping[str, bytes],
        active_kid: str,
        clock: Clock,
        access_ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        if not keys:
            raise TokenConfigError("at least one signing key is required")
        for kid, key in keys.items():
            if len(key) < MIN_KEY_BYTES:
                raise TokenConfigError(f"signing key '{kid}' is shorter than {MIN_KEY_BYTES} bytes")
        if active_kid not in keys:
            raise TokenConfigError("the active kid does not name a signing key")
        self._keys = dict(keys)
        self._active_kid = active_kid
        self._clock = clock
        self._ttl = access_ttl

    @classmethod
    def from_settings(cls, settings: Settings, clock: Clock) -> TokenService:
        """Build the service from ``JWT_SIGNING_KEYS``, ``JWT_ACTIVE_KID`` and the TTL."""
        return cls(
            keys=settings.jwt_keys(),
            active_kid=settings.jwt_active_kid,
            clock=clock,
            access_ttl=timedelta(seconds=settings.access_token_ttl_seconds),
        )

    def issue_access(self, user_id: uuid.UUID, role: str) -> IssuedToken:
        """Sign a new access token for ``user_id``."""
        issued_at = self._clock.now().replace(microsecond=0)
        expires_at = issued_at + self._ttl
        jti = str(uuid.uuid4())
        claims = {
            "sub": str(user_id),
            "role": role,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
            "typ": ACCESS_TYPE,
            "jti": jti,
        }
        token = jwt.encode(
            claims,
            self._keys[self._active_kid],
            algorithm=ALGORITHM,
            headers={"kid": self._active_kid},
        )
        return IssuedToken(token=token, expires_at=expires_at, jti=jti)

    def verify_access(self, token: str) -> AccessClaims:
        """Verify signature, algorithm, kid, required claims, type and expiry.

        Raises:
            InvalidTokenError: For any failure (the reason is never shown to clients).
        """
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise InvalidTokenError("malformed token") from exc
        if header.get("alg") != ALGORITHM:
            raise InvalidTokenError("algorithm not allowed")
        kid = header.get("kid")
        if not isinstance(kid, str) or kid not in self._keys:
            raise InvalidTokenError("unknown key id")
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                self._keys[kid],
                algorithms=[ALGORITHM],
                options={
                    "require": list(REQUIRED_CLAIMS),
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError("signature or claims invalid") from exc
        return self._validate_claims(claims)

    def _validate_claims(self, claims: Mapping[str, Any]) -> AccessClaims:
        if claims.get("typ") != ACCESS_TYPE:
            raise InvalidTokenError("not an access token")
        try:
            user_id = uuid.UUID(str(claims["sub"]))
            issued_at = datetime.fromtimestamp(int(claims["iat"]), UTC)
            expires_at = datetime.fromtimestamp(int(claims["exp"]), UTC)
        except (ValueError, TypeError, OverflowError) as exc:
            raise InvalidTokenError("claims have the wrong shape") from exc
        if self._clock.now() >= expires_at:
            raise InvalidTokenError("token expired")
        return AccessClaims(
            user_id=user_id,
            role=str(claims["role"]),
            jti=str(claims["jti"]),
            issued_at=issued_at,
            expires_at=expires_at,
        )
