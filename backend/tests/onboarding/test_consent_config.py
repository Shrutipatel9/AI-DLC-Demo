"""The consent text comes from configuration; changing it needs new consent (AC4.1.3)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.onboarding.models import ConsentRecord
from app.platform.clock import FrozenClock
from tests.factories import SignedInUser
from tests.onboarding.conftest import bearer, give_consent, put_answer, submit


@pytest.fixture
def settings_overrides(tmp_path: Path) -> dict[str, Any]:
    """Point ONBOARDING_CONSENT_FILE at a changed consent text (consent-v2)."""
    path = tmp_path / "consent_v2.json"
    path.write_text(
        json.dumps({"version": "consent-v2", "text": "New wording.", "agreement": "I agree."}),
        encoding="utf-8",
    )
    return {"ONBOARDING_CONSENT_FILE": str(path)}


def test_changed_consent_text_needs_new_consent_and_records_the_new_version(
    client: TestClient, user: SignedInUser, db_session: Session, frozen_clock: FrozenClock
) -> None:
    # The user agreed to the old text (consent-v1) before the configuration changed.
    db_session.add(
        ConsentRecord(
            user_id=uuid.UUID(user.user_id),
            consent_text_version="consent-v1",
            given_at=frozen_clock.now(),
        )
    )
    db_session.commit()
    state = client.get("/onboarding/consent", headers=bearer(user.access_token)).json()
    assert (state["consentTextVersion"], state["consentText"], state["given"]) == (
        "consent-v2",
        "New wording.",
        False,
    )
    refused = put_answer(client, user, "q1", "Designer")
    assert refused.json()["error"]["code"] == "CONSENT_REQUIRED"
    assert give_consent(client, user)["consentTextVersion"] == "consent-v2"
    assert put_answer(client, user, "q1", "Designer").status_code == 200
    assert submit(client, user).json()["error"]["code"] == "VALIDATION_FAILED"
