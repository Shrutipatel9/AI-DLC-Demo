"""Test data factories. Users are created through the real API and services, so stored
hashes are always genuine (unit-test-instructions: "Test data management")."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.identity.sessions import SessionService
from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender

VALID_PASSWORD = "Sunrise2026x"
COMMON_PASSWORD = "password1"  # on the bundled common-password list


def unique_email(prefix: str = "user") -> str:
    """A fresh address per test (``user-xxxxxxxx@example.test``)."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.test"


@dataclass(frozen=True)
class SignedInUser:
    """A verified user and the access token from the sign-up verification."""

    email: str
    password: str
    full_name: str
    access_token: str
    user_id: str


def register(
    client: TestClient,
    email: str | None = None,
    *,
    password: str = VALID_PASSWORD,
    full_name: str = "Maya Test",
) -> str:
    """Run sign-up step 1 and return the email."""
    address = email or unique_email()
    response = client.post(
        "/auth/register", json={"fullName": full_name, "email": address, "password": password}
    )
    assert response.status_code == 202, response.text
    return address


def make_user(
    client: TestClient,
    fake: RecordingEmailSender,
    *,
    verified: bool = True,
    password: str = VALID_PASSWORD,
    full_name: str = "Maya Test",
) -> SignedInUser | str:
    """Create a user through the API. Returns a :class:`SignedInUser` when verified."""
    email = register(client, password=password, full_name=full_name)
    if not verified:
        return email
    code = fake.last_code_for(email)
    response = client.post("/auth/verify", json={"email": email, "code": code, "purpose": "signup"})
    assert response.status_code == 200, response.text
    body = response.json()
    return SignedInUser(email, password, full_name, body["accessToken"], body["user"]["id"])


def verified_user(client: TestClient, fake: RecordingEmailSender) -> SignedInUser:
    """Shortcut: a verified user."""
    user = make_user(client, fake, verified=True)
    assert isinstance(user, SignedInUser)
    return user


def login_code(
    client: TestClient,
    fake: RecordingEmailSender,
    user: SignedInUser,
    clock: FrozenClock | None = None,
) -> str:
    """Run login step 1 for ``user`` and return the emailed login code."""
    if clock is not None:
        clock.advance(seconds=61)
    response = client.post("/auth/login", json={"email": user.email, "password": user.password})
    assert response.status_code == 202, response.text
    return fake.last_code_for(user.email)


@dataclass(frozen=True)
class IssuedCookie:
    """A real refresh session: the cookie value and its ids."""

    value: str
    token_id: uuid.UUID
    family_id: uuid.UUID


def session_cookie(service: SessionService, session: Session, user_id: uuid.UUID) -> IssuedCookie:
    """Issue a real refresh session (new family) for ``user_id`` and commit it."""
    from app.identity.models import RefreshSession

    token = service.start(session, user_id)
    session.commit()
    row = session.get(RefreshSession, token.token_id)
    assert row is not None
    return IssuedCookie(token.value, token.token_id, row.family_id)
