"""FaceMeasurement: measurements, ears, Hair/Skin/Neck, assessments (US7.3, US7.5, US7.7,
US7.8, US7.10). Real MediaPipe landmarks of the committed synthetic fixtures; no network."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from app.face.public import FaceFound, MediaPipeFaceGeometry, RgbImage
from app.measurement import assessments, features
from app.measurement import landmarks as lm
from app.measurement.geometry import level
from app.measurement.public import (
    FEATURE_KEYS,
    MeasurementError,
    MeasurementService,
    label_for_score,
)
from app.measurement.skin import skin_tone_evenness
from app.platform.settings import DEFAULT_SYMMETRY_BANDS, parse_symmetry_bands
from tests.faces import A_FRONT, A_LEFT, A_RIGHT, MODEL_PATH, NO_FACE, fixture_pixels

BANDS = parse_symmetry_bands(DEFAULT_SYMMETRY_BANDS)
MESH_FEATURES = ("eyebrows", "eyes", "nose", "cheeks", "jaw", "lips", "chin")


@pytest.fixture(scope="module")
def geometry() -> MediaPipeFaceGeometry:
    return MediaPipeFaceGeometry(MODEL_PATH)


@pytest.fixture(scope="module")
def service(geometry: MediaPipeFaceGeometry) -> MeasurementService:
    return MeasurementService(geometry=geometry, decimals=2, bands=BANDS)


@pytest.fixture(scope="module")
def front() -> RgbImage:
    return fixture_pixels(A_FRONT)


@pytest.fixture(scope="module")
def sides() -> dict[str, RgbImage | None]:
    return {"left_3q": fixture_pixels(A_LEFT), "right_3q": fixture_pixels(A_RIGHT)}


@pytest.fixture(scope="module")
def found(geometry: MediaPipeFaceGeometry, front: RgbImage) -> FaceFound:
    result = geometry.detect(front)
    assert isinstance(result, FaceFound)
    return result


def test_all_eleven_features_are_reported_and_the_seven_mesh_features_are_measured(
    service: MeasurementService, front: RgbImage, sides: dict[str, RgbImage | None]
) -> None:
    """AC7.3.1: each mesh feature has geometric measurements from the front photo."""
    result = service.measure(front, sides)

    assert tuple(result["features"]) == FEATURE_KEYS
    for key in MESH_FEATURES:
        feature = result["features"][key]
        assert feature["measured"] is True
        assert feature["source"] == "front"
        assert feature["method"] == "landmark geometry"
        assert len(feature["values"]) >= 3
        assert all(math.isfinite(value) for value in feature["values"].values())


def test_the_same_photos_give_identical_results(
    service: MeasurementService, front: RgbImage, sides: dict[str, RgbImage | None]
) -> None:
    """AC7.3.2, AC7.5.3, AC7.10.2."""
    assert service.measure(front, sides) == service.measure(front, sides)


def test_every_stored_number_is_rounded_to_the_configured_precision(
    geometry: MediaPipeFaceGeometry, front: RgbImage
) -> None:
    coarse = MeasurementService(geometry=geometry, decimals=1, bands=BANDS).measure(front, {})
    for feature in coarse["features"].values():
        for value in feature["values"].values():
            assert value == round(value, 1)


def test_each_ear_is_measured_from_its_own_sides_photo(
    service: MeasurementService, front: RgbImage, sides: dict[str, RgbImage | None]
) -> None:
    """AC7.7.1."""
    ears = service.measure(front, sides)["features"]["ears"]

    assert ears["source"] == {"left": "left_3q", "right": "right_3q"}
    assert set(ears["values"]) == {
        "left_ear_vertical_position_ratio",
        "left_ear_to_eye_distance_ratio",
        "right_ear_vertical_position_ratio",
        "right_ear_to_eye_distance_ratio",
    }


def test_an_ear_whose_side_photo_is_missing_is_measured_from_the_front_photo(
    service: MeasurementService, front: RgbImage, sides: dict[str, RgbImage | None]
) -> None:
    """AC7.7.2."""
    from_sides = service.measure(front, sides)["features"]["ears"]
    only_left = service.measure(front, {"left_3q": sides["left_3q"]})["features"]["ears"]
    none = service.measure(front, {"left_3q": None})["features"]["ears"]

    assert only_left["source"] == {"left": "left_3q", "right": "front"}
    assert none["source"] == {"left": "front", "right": "front"}
    assert (
        only_left["values"]["left_ear_to_eye_distance_ratio"]
        == (from_sides["values"]["left_ear_to_eye_distance_ratio"])
    )
    assert (
        only_left["values"]["right_ear_to_eye_distance_ratio"]
        != (from_sides["values"]["right_ear_to_eye_distance_ratio"])
    )


def test_a_side_photo_without_a_face_also_falls_back_to_the_front_photo(
    service: MeasurementService, front: RgbImage
) -> None:
    ears = service.measure(front, {"left_3q": fixture_pixels(NO_FACE)})["features"]["ears"]
    assert ears["source"]["left"] == "front"


def test_hair_and_neck_say_no_measurement_and_never_invent_a_number(
    service: MeasurementService, front: RgbImage
) -> None:
    """AC7.8.1."""
    result = service.measure(front, {})["features"]
    for key in ("hair", "neck"):
        assert result[key]["measured"] is False
        assert result[key]["values"] == {}
        assert result[key]["method"] == "none"
        assert result[key]["noMeasurementReason"]


def test_skin_uses_a_documented_heuristic_within_zero_to_one_hundred(
    service: MeasurementService, front: RgbImage
) -> None:
    skin = service.measure(front, {})["features"]["skin"]
    assert skin["measured"] is True
    assert skin["method"] == "brightness heuristic"
    assert 0 <= skin["values"]["skin_tone_evenness"] <= 100


def test_skin_says_no_measurement_when_the_face_is_too_far_out_of_frame(
    service: MeasurementService, found: FaceFound, front: RgbImage
) -> None:
    assert skin_tone_evenness(front[:10, :10], found) is None
    blank = np.zeros_like(front)
    assert skin_tone_evenness(blank, found) is None

    class OutOfFrame(MeasurementService):
        def _skin(self, front: RgbImage, found: FaceFound) -> dict:  # type: ignore[type-arg]
            return super()._skin(front[:5, :5], found)

    marker = OutOfFrame(geometry=service.geometry, decimals=2, bands=BANDS).measure(front, {})
    assert marker["features"]["skin"]["measured"] is False
    assert marker["features"]["skin"]["values"] == {}


def test_a_front_photo_without_exactly_one_face_cannot_be_measured(
    service: MeasurementService,
) -> None:
    with pytest.raises(MeasurementError):
        service.measure(fixture_pixels(NO_FACE), {})


def test_symmetry_thirds_dimorphism_prototypicality_and_face_shape_are_stored(
    service: MeasurementService, front: RgbImage
) -> None:
    """AC7.5.1, AC7.10.1."""
    result = service.measure(front, {})["assessments"]

    symmetry = result["symmetry"]
    assert isinstance(symmetry["score"], int)
    assert 0 <= symmetry["score"] <= 100
    assert symmetry["label"] == label_for_score(symmetry["score"], BANDS)
    assert {entry["region"] for entry in symmetry["regionalBalance"]} == set(lm.SYMMETRY_REGIONS)
    assert all(0 <= entry["score"] <= 100 for entry in symmetry["regionalBalance"])
    thirds = result["facialThirds"]
    assert math.isclose(sum(thirds.values()), 1.0, abs_tol=0.02)
    dimorphism = result["dimorphism"]
    assert math.isclose(dimorphism["masculinity"] + dimorphism["femininity"], 100, abs_tol=0.02)
    assert dimorphism["label"] in {"more masculine", "balanced", "more feminine"}
    assert 0 <= result["prototypicality"] <= 100
    assert result["faceShape"] in {"oval", "round", "square", "heart", "diamond", "oblong"}


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (100, "Excellent"),
        (90, "Excellent"),
        (89, "Good"),
        (75, "Good"),
        (74, "Moderate"),
        (55, "Moderate"),
        (54, "Fair"),
        (35, "Fair"),
        (34, "Low"),
        (0, "Low"),
    ],
)
def test_a_score_on_each_band_boundary_gets_the_documented_label(score: int, label: str) -> None:
    """AC7.5.2."""
    assert label_for_score(score, BANDS) == label


def test_bands_are_configuration() -> None:
    custom = parse_symmetry_bands('{"Strong": 50, "Needs care": 0}')
    assert label_for_score(50, custom) == "Strong"
    assert label_for_score(49.99, custom) == "Needs care"


@pytest.mark.parametrize(
    "raw",
    ["not json", "[]", '{"A": 10}', '{"A": 0, "B": 0}', '{"A": 120, "B": 0}', '{"": 0}'],
)
def test_invalid_band_configuration_is_refused(raw: str) -> None:
    with pytest.raises(ValueError, match="SYMMETRY_LABEL_BANDS"):
        parse_symmetry_bands(raw)


def test_a_moved_landmark_lowers_symmetry_and_a_tilted_head_does_not_change_ratios(
    found: FaceFound,
) -> None:
    base = assessments.symmetry(level(found), BANDS)

    moved = list(found.landmarks)
    x, y, z = moved[lm.FACE_EDGE_L]
    moved[lm.FACE_EDGE_L] = (x + 0.06, y, z)
    skewed = assessments.symmetry(level(replace(found, landmarks=tuple(moved))), BANDS)
    assert skewed["score"] < base["score"]

    angle = math.radians(12)
    pts = found.points_px()
    centre = pts.mean(axis=0)
    rotation = np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    rotated_px = (pts - centre) @ rotation.T + centre
    rotated = tuple(
        (px / found.width, py / found.height, z)
        for (px, py), (_x, _y, z) in zip(rotated_px, found.landmarks, strict=True)
    )
    tilted = level(replace(found, landmarks=rotated))
    assert features.eyes(tilted)["eye_width_ratio"] == pytest.approx(
        features.eyes(level(found))["eye_width_ratio"], abs=1e-6
    )


@pytest.mark.parametrize(
    ("length_to_width", "cheek_to_jaw", "forehead", "shape"),
    [
        (1.30, 1.2, 0.85, "oblong"),
        (0.90, 1.2, 0.85, "round"),
        (0.90, 1.05, 0.85, "square"),
        (1.05, 1.35, 0.95, "heart"),
        (1.05, 1.30, 0.75, "diamond"),
        (1.05, 1.05, 0.85, "square"),
        (1.07, 1.22, 0.85, "oval"),
    ],
)
def test_face_shape_rules(
    length_to_width: float, cheek_to_jaw: float, forehead: float, shape: str
) -> None:
    ratios = {
        "face_length_to_width_ratio": length_to_width,
        "cheek_to_jaw_ratio": cheek_to_jaw,
        "forehead_to_cheek_ratio": forehead,
    }
    assert assessments.face_shape(ratios) == shape


def test_dimorphism_and_prototypicality_follow_the_reference() -> None:
    typical = {name: mean for name, (mean, _spread) in assessments.REFERENCE.items()}
    assert assessments.prototypicality(typical) == pytest.approx(100)
    assert assessments.dimorphism(typical)["label"] == "balanced"

    strong = {
        name: assessments.REFERENCE[name][0] + direction * 4 * assessments.REFERENCE[name][1]
        for name, direction in assessments.DIMORPHISM_DIRECTION.items()
    }
    masculine = assessments.dimorphism({**typical, **strong})
    feminine = assessments.dimorphism(
        {
            **typical,
            **{
                name: assessments.REFERENCE[name][0]
                - direction * 4 * assessments.REFERENCE[name][1]
                for name, direction in assessments.DIMORPHISM_DIRECTION.items()
            },
        }
    )
    assert (masculine["label"], feminine["label"]) == ("more masculine", "more feminine")
    far = {
        name: mean + 5 * assessments.REFERENCE[name][1]
        for name, (mean, _s) in assessments.REFERENCE.items()
    }
    assert assessments.prototypicality(far) < 5
