"""Same-person decision over the photo set, written test-first (US5.6; BR-005, ASM-010).

Sources: AC5.6.1 (the 8-case table, [IV] §3), AC5.6.2 (the 0.6 boundary, "within" = <=),
AC5.6.3 (the [IV] §4 worked examples), AC5.6.4 (two angles only). Hub-case tie-break
[Decided by delivery team, U4 plan Step 3]: flag the side whose distance to front is larger;
equal distances flag right.

Angles use the configured ids: ``front``, ``left_3q``, ``right_3q`` (contract C1 PhotoSet).
"""

from __future__ import annotations

import itertools

import pytest

from app.face.public import FaceFound
from app.photos.identity import (
    IdentityResult,
    Signature,
    evaluate_signatures,
    flag_mismatches,
    signature,
    signature_distance,
)

ANGLES = ("front", "left_3q", "right_3q")
THRESHOLD = 0.6
MATCH = 0.30  # same-person pairs measured 0.08-0.33 (ASM-010)
DIFFERENT = 0.90  # different-person pairs measured 0.71-0.93 (ASM-010)


def distances(fr: float, fl: float, rl: float) -> dict[frozenset[str], float]:
    """Pairwise distances keyed by the unordered angle pair."""
    return {
        frozenset({"front", "right_3q"}): fr,
        frozenset({"front", "left_3q"}): fl,
        frozenset({"right_3q", "left_3q"}): rl,
    }


def d(matches: bool) -> float:
    return MATCH if matches else DIFFERENT


# --- AC5.6.1: the 8-case table -------------------------------------------------------------

# (F↔R, F↔L, R↔L) -> flagged angles, in configured order. The hub row (✓ ✓ ✗) is tested
# separately below because its answer depends on the tie-break.
TABLE = [
    ((True, True, True), []),
    ((True, False, False), ["left_3q"]),
    ((False, True, False), ["right_3q"]),
    ((False, False, True), ["front"]),
    ((True, False, True), ["left_3q"]),
    ((False, True, True), ["right_3q"]),
    ((False, False, False), ["left_3q", "right_3q"]),
]


@pytest.mark.parametrize(("pairs", "flagged"), TABLE)
def test_eight_case_table(pairs: tuple[bool, bool, bool], flagged: list[str]) -> None:
    fr, fl, rl = pairs
    assert flag_mismatches(ANGLES, distances(d(fr), d(fl), d(rl)), THRESHOLD) == flagged


def test_hub_case_flags_exactly_one_side_and_never_front() -> None:
    # Front matches both sides, the sides don't match each other ([IV] §3 rule 5).
    flagged = flag_mismatches(ANGLES, distances(MATCH, MATCH, DIFFERENT), THRESHOLD)
    assert len(flagged) == 1
    assert flagged[0] in {"left_3q", "right_3q"}


def test_hub_case_flags_the_side_farther_from_front() -> None:
    assert flag_mismatches(ANGLES, distances(0.50, 0.20, DIFFERENT), THRESHOLD) == ["right_3q"]
    assert flag_mismatches(ANGLES, distances(0.20, 0.50, DIFFERENT), THRESHOLD) == ["left_3q"]


def test_hub_case_with_equal_distances_flags_right() -> None:
    assert flag_mismatches(ANGLES, distances(0.40, 0.40, DIFFERENT), THRESHOLD) == ["right_3q"]


def test_every_combination_flags_front_only_when_both_sides_agree_without_it() -> None:
    # Exhaustive over all 8 combinations: front is flagged only in the (✗, ✗, ✓) row.
    for fr, fl, rl in itertools.product([True, False], repeat=3):
        flagged = flag_mismatches(ANGLES, distances(d(fr), d(fl), d(rl)), THRESHOLD)
        assert ("front" in flagged) == (not fr and not fl and rl), (fr, fl, rl)
        if fr and fl and rl:
            assert flagged == []
        else:
            assert flagged, (fr, fl, rl)


# --- AC5.6.2: the threshold boundary ---------------------------------------------------------


def test_distance_exactly_at_the_threshold_is_a_match() -> None:
    assert flag_mismatches(ANGLES, distances(0.6, MATCH, MATCH), THRESHOLD) == []


def test_distance_just_above_the_threshold_is_not_a_match() -> None:
    flagged = flag_mismatches(ANGLES, distances(0.6 + 1e-9, MATCH, MATCH), THRESHOLD)
    assert flagged == ["right_3q"]  # (✗ ✓ ✓): left is the hub, right is the odd one out


def test_threshold_comes_from_the_argument_not_a_constant() -> None:
    # A stricter configured threshold turns the same distances into a mismatch (AC5.5.3).
    assert flag_mismatches(ANGLES, distances(0.5, 0.5, 0.5), 0.6) == []
    assert flag_mismatches(ANGLES, distances(0.5, 0.5, 0.5), 0.4) == ["left_3q", "right_3q"]


# --- AC5.6.3: the [IV] §4 worked examples, through signatures -------------------------------

# Three clearly different people (pairwise L1 >= 0.8) and a small same-person jitter.
PEOPLE: dict[str, Signature] = {
    "A": (0.40, 0.70, 0.80, 2.00, 2.40),
    "B": (0.45, 0.85, 1.00, 2.20, 2.60),
    "C": (0.35, 0.60, 0.65, 1.75, 2.15),
}
JITTER = {"front": 0.0, "left_3q": 0.02, "right_3q": -0.02}


def photo_set(front: str, right: str, left: str) -> dict[str, Signature]:
    """Signatures for a set given as in [IV] §4 (columns front, right, left)."""
    chosen = {"front": front, "right_3q": right, "left_3q": left}
    return {
        angle: tuple(value + JITTER[angle] for value in PEOPLE[person])  # type: ignore[misc]
        for angle, person in chosen.items()
    }


def flagged_for(front: str, right: str, left: str) -> list[str]:
    result = evaluate_signatures(ANGLES, photo_set(front, right, left), THRESHOLD)
    return list(result.mismatched_angles)


def test_people_are_separated_and_jitter_stays_within_the_threshold() -> None:
    for first, second in itertools.combinations(PEOPLE.values(), 2):
        assert signature_distance(first, second) > THRESHOLD
    same = photo_set("A", "A", "A")
    for first, second in itertools.combinations(same.values(), 2):
        assert signature_distance(first, second) <= THRESHOLD


def test_scene_1_2_3_sequential_retakes() -> None:
    assert flagged_for("A", "B", "C") == ["left_3q", "right_3q"]  # front kept
    assert flagged_for("B", "B", "C") == ["left_3q"]  # retake front -> B
    assert flagged_for("B", "B", "B") == []  # retake left -> B: Continue enabled


def test_flip_flop_a_reference_is_not_tied_to_fronts_original_identity() -> None:
    assert flagged_for("A", "B", "A") == ["right_3q"]
    assert flagged_for("B", "B", "A") == ["left_3q"]  # retake front -> B


def test_flip_flop_b_retake_moves_the_error_to_an_untouched_angle() -> None:
    assert flagged_for("A", "A", "B") == ["left_3q"]
    assert flagged_for("A", "B", "B") == ["front"]  # retake right -> B: front flagged


def test_consistent_set_reports_consistent() -> None:
    result = evaluate_signatures(ANGLES, photo_set("A", "A", "A"), THRESHOLD)
    assert result == IdentityResult(status="consistent", mismatched_angles=())


def test_mismatched_set_reports_mismatch_status() -> None:
    result = evaluate_signatures(ANGLES, photo_set("A", "B", "A"), THRESHOLD)
    assert result.status == "mismatch"
    assert result.mismatched_angles == ("right_3q",)


# --- AC5.6.4: two angles only ----------------------------------------------------------------


def test_two_angles_only_does_not_run_and_does_not_block() -> None:
    signatures = photo_set("A", "B", "A")
    del signatures["left_3q"]  # only front and right have passed
    result = evaluate_signatures(ANGLES, signatures, THRESHOLD)
    assert result == IdentityResult(status="incomplete", mismatched_angles=())


def test_no_photos_is_incomplete() -> None:
    assert evaluate_signatures(ANGLES, {}, THRESHOLD).status == "incomplete"


def test_extra_signatures_for_unconfigured_angles_are_ignored() -> None:
    signatures = photo_set("A", "A", "A") | {"profile": PEOPLE["C"]}
    assert evaluate_signatures(ANGLES, signatures, THRESHOLD).status == "consistent"


# --- The 5-ratio landmark signature (ASM-010) -------------------------------------------------


def face_with(
    points: dict[int, tuple[float, float]], width: int = 1000, height: int = 1000
) -> FaceFound:
    """A face whose named landmarks sit at the given pixel positions (others at the centre)."""
    landmarks = [(0.5, 0.5, 0.0)] * 478
    for index, (x, y) in points.items():
        landmarks[index] = (x / width, y / height, 0.0)
    return FaceFound(landmarks=tuple(landmarks), width=width, height=height, yaw_degrees=0.0)


#: Eye corners 33/133 (one eye) and 362/263 (the other); nose 129/358; mouth 61/291;
#: jaw 172/397; face edges 234/454. Eye centres are 100 px apart (inter-eye distance).
BASE_POINTS = {
    33: (420.0, 400.0),
    133: (460.0, 400.0),
    362: (520.0, 400.0),
    263: (560.0, 400.0),
    129: (465.0, 480.0),
    358: (535.0, 480.0),
    61: (450.0, 560.0),
    291: (550.0, 560.0),
    172: (400.0, 600.0),
    397: (600.0, 600.0),
    234: (370.0, 450.0),
    454: (630.0, 450.0),
}


def test_signature_is_five_widths_over_the_inter_eye_distance() -> None:
    eye, nose, mouth, jaw, face = signature(face_with(BASE_POINTS))
    assert eye == pytest.approx(0.40)  # 40 px eye width / 100 px
    assert nose == pytest.approx(0.70)
    assert mouth == pytest.approx(1.00)
    assert jaw == pytest.approx(2.00)
    assert face == pytest.approx(2.60)


def test_signature_does_not_change_with_photo_scale() -> None:
    doubled = {index: (x * 2, y * 2) for index, (x, y) in BASE_POINTS.items()}
    small = signature(face_with(BASE_POINTS))
    large = signature(face_with(doubled, width=2000, height=2000))
    assert large == pytest.approx(small)


def test_signature_uses_pixels_not_normalised_coordinates() -> None:
    # The same pixel geometry in a non-square image gives the same signature.
    wide = signature(face_with(BASE_POINTS, width=1600, height=1000))
    assert wide == pytest.approx(signature(face_with(BASE_POINTS)))


def test_distance_is_the_sum_of_absolute_ratio_differences() -> None:
    first: Signature = (0.4, 0.7, 1.0, 2.0, 2.6)
    second: Signature = (0.5, 0.6, 1.2, 2.0, 2.3)
    assert signature_distance(first, second) == pytest.approx(0.1 + 0.1 + 0.2 + 0.0 + 0.3)
    assert signature_distance(second, first) == signature_distance(first, second)
    assert signature_distance(first, first) == 0.0


def test_signature_refuses_a_face_with_no_inter_eye_distance() -> None:
    collapsed = dict(BASE_POINTS)
    for index in (33, 133, 362, 263):
        collapsed[index] = (500.0, 400.0)
    with pytest.raises(ValueError, match="inter-eye"):
        signature(face_with(collapsed))
