"""Configuration drives the photo steps and limits with no code change (AC5.2.1, AC5.5.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.photos.public import build_photos
from app.platform.clock import FrozenClock
from tests.faces import A_FRONT, A_RIGHT, OVERRIDES_PATH, require_downloads
from tests.factories import SignedInUser
from tests.helpers import make_settings
from tests.photos.conftest import bearer, upload


@pytest.fixture
def settings_overrides(media_root: Path) -> dict[str, Any]:
    """Two angles and a 1 MB upload limit."""
    require_downloads()
    return {
        "MEDIA_ROOT": str(media_root),
        "FACE_LANDMARK_OVERRIDES_FILE": str(OVERRIDES_PATH),
        "PHOTO_ANGLES": "front,right_3q",
        "PHOTO_MAX_UPLOAD_BYTES": str(1024 * 1024),
    }


def test_the_configured_angles_are_the_steps(client: TestClient, submitted: SignedInUser) -> None:
    requirements = client.get("/photos/requirements", headers=bearer(submitted.access_token))
    assert [angle["id"] for angle in requirements.json()["angles"]] == ["front", "right_3q"]
    assert requirements.json()["maxUploadBytes"] == 1024 * 1024
    body = client.get("/photos", headers=bearer(submitted.access_token)).json()
    assert body["requiredAngles"] == ["front", "right_3q"]
    assert upload(client, submitted, "left_3q", A_FRONT).status_code == 404


def test_a_two_angle_set_completes_with_two_photos(
    client: TestClient, submitted: SignedInUser
) -> None:
    upload(client, submitted, "front", A_FRONT)
    body = upload(client, submitted, "right_3q", A_RIGHT).json()
    assert body["acceptedCount"] == 2
    assert body["identity"]["status"] == "consistent"


def test_the_configured_upload_limit_applies(client: TestClient, submitted: SignedInUser) -> None:
    response = upload(client, submitted, "front", data=b"\xff\xd8\xff" + b"0" * (1024 * 1024))
    assert response.status_code == 413
    assert "1 MB" in response.json()["error"]["message"]


def test_build_photos_refuses_an_angle_missing_from_the_catalog(
    tmp_path: Path, frozen_clock: FrozenClock
) -> None:
    from app.face.public import build_face_geometry
    from app.media.public import build_media_store
    from app.photos.catalog import CatalogError

    settings = make_settings(PHOTO_ANGLES="front,profile", MEDIA_ROOT=str(tmp_path))
    clock = frozen_clock
    with pytest.raises(CatalogError, match="profile"):
        build_photos(
            settings,
            clock=clock,
            media=build_media_store(settings, clock=clock),
            geometry=build_face_geometry(settings),
        )
