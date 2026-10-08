"""The photo catalog and the U4 settings (AC5.2.1, AC5.5.3, AC5.9.1, AC5.9.2; ASM-005).

Bad configuration fails at start-up with a message naming the setting, never at request time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.photos.catalog import DEFAULT_CATALOG_FILE, CatalogError, load_catalog
from app.platform.settings import parse_yaw_ranges
from tests.helpers import make_settings


def bundled() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(DEFAULT_CATALOG_FILE.read_text(encoding="utf-8"))
    return data


def write_catalog(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_the_bundled_catalog_has_the_seven_rules_and_three_angles() -> None:
    catalog = load_catalog(DEFAULT_CATALOG_FILE, ["front", "left_3q", "right_3q"])
    assert [rule.id for rule in catalog.rules] == [
        "no_glasses_hat",
        "even_light",
        "white_background",
        "hair_back",
        "no_makeup",
        "no_neck_cover",
        "no_filters",
    ]
    assert len(catalog.guidance) == 9
    assert catalog.angle_ids == ["front", "left_3q", "right_3q"]
    front = catalog.angle("front")
    assert front is not None
    assert (front.yaw_min, front.yaw_max) == (-12.0, 12.0)
    assert catalog.angle("profile") is None


def test_the_configured_order_and_subset_drive_the_steps() -> None:
    catalog = load_catalog(DEFAULT_CATALOG_FILE, ["right_3q", "front"])
    assert catalog.angle_ids == ["right_3q", "front"]


def test_settings_default_to_the_three_angles_and_accept_a_list() -> None:
    assert make_settings().photo_angles == ["front", "left_3q", "right_3q"]
    assert make_settings(PHOTO_ANGLES="front, right_3q").photo_angles == ["front", "right_3q"]


def test_an_unknown_configured_angle_fails_start_up() -> None:
    with pytest.raises(CatalogError, match="profile"):
        load_catalog(DEFAULT_CATALOG_FILE, ["front", "profile"])
    with pytest.raises(CatalogError, match="profile"):
        load_catalog(DEFAULT_CATALOG_FILE, ["front"], {"profile": (-5.0, 5.0)})


def test_a_seven_angle_set_is_a_catalog_change_not_a_code_change(tmp_path: Path) -> None:
    data = bundled()
    data["angles"].append(
        {
            "id": "left_profile",
            "label": "Left profile",
            "instruction": "Turn your head fully to your right.",
            "turnHint": "Turn your head fully to your right.",
            "illustration": "left",
            "yawRange": [-90, -50],
        }
    )
    catalog = load_catalog(write_catalog(tmp_path, data), ["front", "left_profile"])
    assert catalog.angle_ids == ["front", "left_profile"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.update(rules=[]), "rules"),
        (lambda d: d.update(rules=["text only"]), "rule"),
        (lambda d: d.update(guidance="one string"), "guidance"),
        (lambda d: d.update(angles=[]), "angles"),
        (lambda d: d["angles"][0].update(yawRange=[10, -10]), "yawRange"),
        (lambda d: d["angles"][0].update(illustration="up"), "illustration"),
        (lambda d: d["angles"][0].update(label=" "), "label"),
        (lambda d: d["angles"].__setitem__(0, "front"), "object"),
        (lambda d: d.pop("version"), "version"),
    ],
)
def test_an_invalid_catalog_is_refused(tmp_path: Path, mutate: Any, message: str) -> None:
    data = bundled()
    mutate(data)
    with pytest.raises(CatalogError, match=message):
        load_catalog(write_catalog(tmp_path, data), ["front"])


def test_an_unreadable_catalog_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="cannot read"):
        load_catalog(tmp_path / "absent.json", ["front"])
    with pytest.raises(CatalogError, match="JSON object"):
        load_catalog(write_catalog(tmp_path, [1, 2]), ["front"])


def test_identity_and_per_photo_thresholds_come_from_settings() -> None:
    settings = make_settings(IDENTITY_THRESHOLD="0.45", PHOTO_MAX_UPLOAD_BYTES="2048")
    assert settings.identity_threshold == 0.45
    assert settings.photo_max_upload_bytes == 2048
    assert make_settings().identity_threshold == 0.6


def test_yaw_range_overrides_are_parsed() -> None:
    settings = make_settings(PHOTO_POSE_YAW_RANGES='{"front": [-8, 8]}')
    assert settings.yaw_range_overrides() == {"front": (-8.0, 8.0)}
    assert make_settings().yaw_range_overrides() == {}
    assert make_settings(PHOTO_POSE_YAW_RANGES=" ").yaw_range_overrides() == {}


@pytest.mark.parametrize(
    "raw", ["not json", "[1]", '{"Front": [-1, 1]}', '{"front": [5, -5]}', '{"front": [true, 2]}']
)
def test_invalid_yaw_ranges_are_refused(raw: str) -> None:
    with pytest.raises(ValueError, match="PHOTO_POSE_YAW_RANGES"):
        parse_yaw_ranges(raw)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"PHOTO_ANGLES": ""}, "at least one angle"),
        ({"PHOTO_ANGLES": "front,front"}, "repeat"),
        ({"PHOTO_ANGLES": "Front"}, "look like"),
        ({"PHOTO_MIN_BRIGHTNESS": "200", "PHOTO_MAX_BRIGHTNESS": "100"}, "BRIGHTNESS"),
        ({"PHOTO_MIN_FACE_FRACTION": "0.5", "PHOTO_MAX_FACE_FRACTION": "0.4"}, "FACE_FRACTION"),
        ({"PHOTO_POSE_YAW_RANGES": "[]"}, "PHOTO_POSE_YAW_RANGES"),
    ],
)
def test_invalid_photo_settings_are_refused(overrides: dict[str, str], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        make_settings(**overrides)


def test_landmark_overrides_are_refused_outside_development_and_test(tmp_path: Path) -> None:
    production = {
        "APP_ENV": "production",
        "EMAIL_BACKEND": "smtp",
        "SMTP_STARTTLS": "true",
        "REFRESH_COOKIE_SECURE": "true",
        "RATE_LIMIT_BACKEND": "postgres",
        # U5: the payment fake is refused in production too.
        "PAYMENT_PROVIDER": "stripe",
        "STRIPE_SECRET_KEY": "sk_test_unused",
        "STRIPE_WEBHOOK_SECRET": "whsec_placeholder",
        # U6: the AI fakes are refused in production too.
        "AI_TEXT_PROVIDER": "openai",
        "AI_IMAGE_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test-unused",
        "OPENAI_TEXT_MODEL": "text-model",
        "OPENAI_IMAGE_MODEL": "image-model",
    }
    make_settings(**production)  # valid without the overrides file
    with pytest.raises(ValidationError, match="FACE_LANDMARK_OVERRIDES_FILE"):
        make_settings(**production, FACE_LANDMARK_OVERRIDES_FILE=str(tmp_path / "o.json"))
    assert make_settings(FACE_LANDMARK_OVERRIDES_FILE="").face_landmark_overrides_file is None
