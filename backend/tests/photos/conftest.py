"""Photo test fixtures: the real app (identity fixtures), real PostgreSQL, the real MediaPipe
model, a private media root per test, and users who have submitted the questionnaire.

The landmark overrides file is enabled for the API tests, so the person-B fixture reads as a
different person (see ``app.face.overrides``); every other image goes to the real model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.onboarding.definition import QuestionnaireDefinition
from app.platform.email.fake import RecordingEmailSender
from tests.faces import OVERRIDES_PATH, fixture_bytes, require_downloads
from tests.factories import SignedInUser, verified_user
from tests.identity.conftest import (  # noqa: F401  (pytest fixtures re-used here)
    app,
    bearer,
    client,
    email_fake,
)
from tests.onboarding.conftest import (  # noqa: F401  (pytest fixtures re-used here)
    answer_all,
    give_consent,
    seed_definition,
    submit,
)

ANGLES = ["front", "left_3q", "right_3q"]


@pytest.fixture
def media_root(tmp_path: Path) -> Path:
    """A fresh private storage directory for this test's app."""
    root = tmp_path / "media"
    root.mkdir()
    return root


@pytest.fixture
def settings_overrides(media_root: Path) -> dict[str, Any]:
    """The photo app: private media root and the E2E landmark overrides."""
    require_downloads()
    return {"MEDIA_ROOT": str(media_root), "FACE_LANDMARK_OVERRIDES_FILE": str(OVERRIDES_PATH)}


def submitted_user_for(
    api: TestClient, fake: RecordingEmailSender, definition: QuestionnaireDefinition
) -> SignedInUser:
    """A verified user who consented and submitted the questionnaire."""
    user = verified_user(api, fake)
    give_consent(api, user)
    answer_all(api, user, definition)
    response = submit(api, user)
    assert response.status_code == 200, response.text
    return user


@pytest.fixture
def submitted(
    client: TestClient,  # noqa: F811
    email_fake: RecordingEmailSender,  # noqa: F811
    seed_definition: QuestionnaireDefinition,  # noqa: F811
) -> SignedInUser:
    """A signed-in user whose questionnaire is submitted (photos are the next step)."""
    return submitted_user_for(client, email_fake, seed_definition)


def upload(
    api: TestClient,
    user: SignedInUser,
    angle: str,
    name: str | None = None,
    *,
    data: bytes | None = None,
    filename: str = "photo.png",
    content_type: str = "image/png",
    capture_method: str | None = None,
) -> Any:
    """PUT one photo (a committed fixture by ``name``, or raw ``data``)."""
    body = data if data is not None else fixture_bytes(name or "")
    form: dict[str, str] = {}
    if capture_method is not None:
        form["captureMethod"] = capture_method
    return api.put(
        f"/photos/{angle}",
        files={"file": (filename, body, content_type)},
        data=form,
        headers=bearer(user.access_token),
    )


def photo_status(body: dict[str, Any], angle: str) -> dict[str, Any]:
    """The ``photos[]`` entry for ``angle`` in a PhotoSet body."""
    entry: dict[str, Any] = next(photo for photo in body["photos"] if photo["angle"] == angle)
    return entry
