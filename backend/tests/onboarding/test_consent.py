"""Consent gate (US4.1; AC4.1.1-AC4.1.3; plan decision D2)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.onboarding.models import ConsentRecord
from app.platform.clock import FrozenClock
from tests.factories import SignedInUser
from tests.onboarding.conftest import bearer, give_consent


def test_consent_state_before_consent_shows_the_configured_text(
    client: TestClient, user: SignedInUser
) -> None:
    response = client.get("/onboarding/consent", headers=bearer(user.access_token))
    assert response.status_code == 200
    body = response.json()
    assert body["consentTextVersion"] == "consent-v1"
    assert "Health-related answers never leave the platform" in body["consentText"]
    assert body["agreementText"].startswith("I agree")
    assert body["given"] is False
    assert body["givenAt"] is None
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/onboarding/questionnaire", None),
        ("GET", "/onboarding/response", None),
        ("PUT", "/onboarding/response/answers/q1", {"value": "Designer"}),
        ("POST", "/onboarding/response/submit", {"disclaimerConfirmed": True}),
    ],
)
def test_questionnaire_actions_without_consent_are_refused(
    client: TestClient, user: SignedInUser, method: str, path: str, body: object
) -> None:
    response = client.request(method, path, json=body, headers=bearer(user.access_token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_consent_is_stored_with_time_and_version_once(
    client: TestClient,
    user: SignedInUser,
    frozen_clock: FrozenClock,
    db_session: Session,
) -> None:
    first = give_consent(client, user)
    assert first["given"] is True
    assert first["givenAt"].startswith("2026-10-01T10:00:00")
    frozen_clock.advance(minutes=5)
    again = give_consent(client, user)
    assert again["givenAt"] == first["givenAt"]
    rows = db_session.scalars(
        select(ConsentRecord).where(ConsentRecord.user_id == uuid.UUID(user.user_id))
    ).all()
    assert [(r.consent_text_version, r.given_at.isoformat()) for r in rows] == [
        ("consent-v1", "2026-10-01T10:00:00+00:00")
    ]
    state = client.get("/onboarding/consent", headers=bearer(user.access_token)).json()
    assert state["given"] is True
    assert (
        client.get("/onboarding/questionnaire", headers=bearer(user.access_token)).status_code
        == 200
    )


def test_consent_to_an_out_of_date_version_is_refused(
    client: TestClient, user: SignedInUser
) -> None:
    response = client.post(
        "/onboarding/consent",
        json={"consentTextVersion": "consent-v0"},
        headers=bearer(user.access_token),
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "CONSENT_REQUIRED"
    assert error["details"] == [{"reason": "CONSENT_VERSION_CHANGED"}]
