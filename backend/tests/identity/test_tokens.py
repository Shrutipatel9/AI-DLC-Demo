"""JWT (access token) service — written test-first (team Testing Posture, Step 12).

Acceptance criteria: AC3.2.1 (access token on verify), AC3.8.2 (no token, expired,
tampered, ``alg: none`` and reset tokens are refused); rules BR4.1, BR4.3; NFR2.6;
AUTH-010-AUTH-012.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import timedelta
from typing import Any

import jwt
import pytest

from app.identity.tokens import InvalidTokenError, TokenConfigError, TokenService
from app.platform.clock import FrozenClock
from tests.helpers import make_settings

KEY_1 = secrets.token_bytes(48)
KEY_2 = secrets.token_bytes(48)
USER = uuid.UUID("0b3e2d4c-1111-4222-8333-444455556666")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _forge(header: dict[str, Any], payload: dict[str, Any], key: bytes | None) -> str:
    head = _b64(json.dumps(header).encode())
    body = _b64(json.dumps(payload).encode())
    signing_input = f"{head}.{body}".encode()
    signature = _b64(hmac.new(key, signing_input, hashlib.sha256).digest()) if key else ""
    return f"{head}.{body}.{signature}"


@pytest.fixture
def service(frozen_clock: FrozenClock) -> TokenService:
    return TokenService(keys={"k1": KEY_1}, active_kid="k1", clock=frozen_clock)


def test_access_token_claims_and_header(service: TokenService, frozen_clock: FrozenClock) -> None:
    issued = service.issue_access(USER, "user")
    header = jwt.get_unverified_header(issued.token)
    claims = jwt.decode(issued.token, options={"verify_signature": False})
    now = int(frozen_clock.now().timestamp())
    assert header["alg"] == "HS256"
    assert header["kid"] == "k1"
    assert claims["sub"] == str(USER)
    assert claims["role"] == "user"
    assert claims["typ"] == "access"
    assert claims["iat"] == now
    assert claims["exp"] == now + 15 * 60
    assert uuid.UUID(claims["jti"])
    assert issued.expires_at == frozen_clock.now() + timedelta(minutes=15)
    verified = service.verify_access(issued.token)
    assert verified.user_id == USER
    assert verified.role == "user"
    assert verified.jti == claims["jti"]


def test_each_token_has_a_unique_id(service: TokenService) -> None:
    assert service.issue_access(USER, "user").jti != service.issue_access(USER, "user").jti


def test_valid_at_fourteen_fifty_nine_invalid_at_fifteen(
    service: TokenService, frozen_clock: FrozenClock
) -> None:
    token = service.issue_access(USER, "user").token
    frozen_clock.advance(minutes=14, seconds=59)
    assert service.verify_access(token).user_id == USER
    frozen_clock.advance(seconds=1)
    with pytest.raises(InvalidTokenError):
        service.verify_access(token)


def test_alg_none_is_refused(service: TokenService, frozen_clock: FrozenClock) -> None:
    now = int(frozen_clock.now().timestamp())
    payload = {
        "sub": str(USER),
        "role": "user",
        "typ": "access",
        "iat": now,
        "exp": now + 900,
        "jti": "x",
    }
    token = _forge({"alg": "none", "typ": "JWT", "kid": "k1"}, payload, None)
    with pytest.raises(InvalidTokenError):
        service.verify_access(token)


def test_other_algorithms_are_refused(service: TokenService, frozen_clock: FrozenClock) -> None:
    now = int(frozen_clock.now().timestamp())
    payload = {
        "sub": str(USER),
        "role": "user",
        "typ": "access",
        "iat": now,
        "exp": now + 900,
        "jti": "x",
    }
    for alg in ("RS256", "HS512", "ES256"):
        token = _forge({"alg": alg, "typ": "JWT", "kid": "k1"}, payload, KEY_1)
        with pytest.raises(InvalidTokenError):
            service.verify_access(token)


def test_tampered_signature_and_payload_are_refused(service: TokenService) -> None:
    token = service.issue_access(USER, "user").token
    head, body, signature = token.split(".")
    flipped = signature[:-2] + ("AA" if signature[-2:] != "AA" else "BB")
    with pytest.raises(InvalidTokenError):
        service.verify_access(f"{head}.{body}.{flipped}")
    claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    claims["role"] = "admin"
    forged_body = _b64(json.dumps(claims).encode())
    with pytest.raises(InvalidTokenError):
        service.verify_access(f"{head}.{forged_body}.{signature}")


def test_token_signed_with_another_key_is_refused(frozen_clock: FrozenClock) -> None:
    attacker = TokenService(
        keys={"k1": secrets.token_bytes(48)}, active_kid="k1", clock=frozen_clock
    )
    service = TokenService(keys={"k1": KEY_1}, active_kid="k1", clock=frozen_clock)
    with pytest.raises(InvalidTokenError):
        service.verify_access(attacker.issue_access(USER, "user").token)


@pytest.mark.parametrize("typ", ["reset", "refresh", None])
def test_wrong_token_type_is_refused(
    service: TokenService, frozen_clock: FrozenClock, typ: str | None
) -> None:
    now = int(frozen_clock.now().timestamp())
    payload: dict[str, Any] = {
        "sub": str(USER),
        "role": "user",
        "iat": now,
        "exp": now + 900,
        "jti": "x",
    }
    if typ is not None:
        payload["typ"] = typ
    token = _forge({"alg": "HS256", "typ": "JWT", "kid": "k1"}, payload, KEY_1)
    with pytest.raises(InvalidTokenError):
        service.verify_access(token)


def test_unknown_or_missing_kid_is_refused(
    service: TokenService, frozen_clock: FrozenClock
) -> None:
    now = int(frozen_clock.now().timestamp())
    payload = {
        "sub": str(USER),
        "role": "user",
        "typ": "access",
        "iat": now,
        "exp": now + 900,
        "jti": "x",
    }
    with pytest.raises(InvalidTokenError):
        service.verify_access(_forge({"alg": "HS256", "kid": "k9"}, payload, KEY_1))
    with pytest.raises(InvalidTokenError):
        service.verify_access(_forge({"alg": "HS256"}, payload, KEY_1))


@pytest.mark.parametrize("bad", ["", "not-a-token", "a.b", "a.b.c.d", "...."])
def test_garbage_is_refused(service: TokenService, bad: str) -> None:
    with pytest.raises(InvalidTokenError):
        service.verify_access(bad)


def test_missing_required_claims_are_refused(
    service: TokenService, frozen_clock: FrozenClock
) -> None:
    now = int(frozen_clock.now().timestamp())
    full = {
        "sub": str(USER),
        "role": "user",
        "typ": "access",
        "iat": now,
        "exp": now + 900,
        "jti": "x",
    }
    for missing in ("sub", "exp", "iat", "typ"):
        payload = {k: v for k, v in full.items() if k != missing}
        with pytest.raises(InvalidTokenError):
            service.verify_access(_forge({"alg": "HS256", "kid": "k1"}, payload, KEY_1))
    bad_sub = {**full, "sub": "not-a-uuid"}
    with pytest.raises(InvalidTokenError):
        service.verify_access(_forge({"alg": "HS256", "kid": "k1"}, bad_sub, KEY_1))


def test_rotation_accepts_both_keys_during_overlap(frozen_clock: FrozenClock) -> None:
    old = TokenService(keys={"k1": KEY_1}, active_kid="k1", clock=frozen_clock)
    old_token = old.issue_access(USER, "user").token
    rotated = TokenService(keys={"k1": KEY_1, "k2": KEY_2}, active_kid="k2", clock=frozen_clock)
    new_token = rotated.issue_access(USER, "user").token
    assert jwt.get_unverified_header(new_token)["kid"] == "k2"
    assert rotated.verify_access(old_token).user_id == USER
    assert rotated.verify_access(new_token).user_id == USER
    retired = TokenService(keys={"k2": KEY_2}, active_kid="k2", clock=frozen_clock)
    with pytest.raises(InvalidTokenError):
        retired.verify_access(old_token)


def test_start_up_refuses_short_key_or_missing_active_kid(frozen_clock: FrozenClock) -> None:
    with pytest.raises(TokenConfigError):
        TokenService(keys={"k1": secrets.token_bytes(31)}, active_kid="k1", clock=frozen_clock)
    with pytest.raises(TokenConfigError):
        TokenService(keys={"k1": KEY_1}, active_kid="k2", clock=frozen_clock)
    with pytest.raises(TokenConfigError):
        TokenService(keys={}, active_kid="k1", clock=frozen_clock)


def test_built_from_settings(frozen_clock: FrozenClock) -> None:
    settings = make_settings(ACCESS_TOKEN_TTL_SECONDS="600")
    service = TokenService.from_settings(settings, frozen_clock)
    issued = service.issue_access(USER, "user")
    assert issued.expires_at == frozen_clock.now() + timedelta(seconds=600)
    assert service.verify_access(issued.token).user_id == USER
