"""Same-person check over the photo set (US5.6; BR-005, ASM-010, [IV] §1-§5).

Pure functions, no state: the caller computes fresh signatures from the photos stored
right now, every time ([IV] §1, AC5.6.5). Nothing here is cached.

**Signature (ASM-010).** Five landmark widths, each divided by the inter-eye distance
(the distance between the two eye centres): eye width, nose width, mouth width, jaw width
and face width. Measured in pixels, so the image's aspect ratio does not matter.

**Distance.** [Decided by delivery team] The sum of the absolute differences of the five
ratios (L1). The client's documented ranges (same person 0.08-0.33, different people
0.71-0.93, threshold 0.6) do not name the metric; L1 reproduces them on our fixtures (the
Euclidean distance compresses different people to about 0.5). A pair matches when its
distance is <= the threshold ([Assumption] "within" means <=, AC5.6.2).

**Decision ([IV] §3).** Keep the largest group of photos that all match each other and
flag every photo outside it. Among equally large groups:

1. prefer a group that contains the first configured angle (front): with no agreeing pair
   front is the kept reference ([IV] §3 rule 4), and front is protected in the hub case;
2. then the group whose photos are closest together: in the hub case (front matches both
   sides, the sides don't match each other) the side farther from front is flagged
   ([Decided by delivery team], U4 plan Step 3);
3. then configured order, so equal distances keep left and flag right.

This reproduces the 8-case table of AC5.6.1 and the [IV] §4 worked examples.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.face.public import FaceFound

#: (eye width, nose width, mouth width, jaw width, face width) / inter-eye distance.
Signature = tuple[float, float, float, float, float]
IdentityStatus = Literal["incomplete", "consistent", "mismatch"]

# MediaPipe face mesh indices (canonical 478-point topology).
_EYE_A = (33, 133)  # outer and inner corner of one eye
_EYE_B = (362, 263)  # inner and outer corner of the other eye
_NOSE = (129, 358)  # nose wings
_MOUTH = (61, 291)  # mouth corners
_JAW = (172, 397)  # jaw angles
_FACE = (234, 454)  # face edges at the cheekbones

_MIN_INTER_EYE_PX = 1e-6


@dataclass(frozen=True)
class IdentityResult:
    """The same-person result for the current photo set (contract C4 ``IdentityResult``).

    ``incomplete`` means not every required angle has an accepted photo: the check did not
    run and blocks nothing yet (AC5.6.4).
    """

    status: IdentityStatus
    mismatched_angles: tuple[str, ...]


def signature(face: FaceFound) -> Signature:
    """The 5-ratio landmark signature of a face (ASM-010).

    Raises:
        ValueError: When the eye centres coincide, so no ratio can be formed.
    """
    points = face.points_px()

    def width(pair: tuple[int, int]) -> float:
        return float(np.linalg.norm(points[pair[0]] - points[pair[1]]))

    centre_a = (points[_EYE_A[0]] + points[_EYE_A[1]]) / 2
    centre_b = (points[_EYE_B[0]] + points[_EYE_B[1]]) / 2
    inter_eye = float(np.linalg.norm(centre_a - centre_b))
    if inter_eye <= _MIN_INTER_EYE_PX:
        raise ValueError("the inter-eye distance is zero; no signature can be formed")
    eye = (width(_EYE_A) + width(_EYE_B)) / 2
    return (
        eye / inter_eye,
        width(_NOSE) / inter_eye,
        width(_MOUTH) / inter_eye,
        width(_JAW) / inter_eye,
        width(_FACE) / inter_eye,
    )


def signature_distance(first: Signature, second: Signature) -> float:
    """L1 distance between two signatures (see the module docstring)."""
    return float(sum(abs(a - b) for a, b in zip(first, second, strict=True)))


def flag_mismatches(
    angles: Sequence[str], distances: Mapping[frozenset[str], float], threshold: float
) -> list[str]:
    """The angles to flag, in configured order; an empty list means the set is consistent.

    Args:
        angles: The required angles in configured order (the first is the reference).
        distances: The distance for every unordered pair of ``angles``.
        threshold: A pair matches when its distance is <= this.
    """
    order = list(angles)

    def distance(first: str, second: str) -> float:
        return distances[frozenset({first, second})]

    def agrees(group: tuple[str, ...]) -> bool:
        return all(distance(a, b) <= threshold for a, b in itertools.combinations(group, 2))

    for size in range(len(order), 0, -1):
        groups = [g for g in itertools.combinations(order, size) if agrees(g)]
        if groups:
            kept = min(
                groups,
                key=lambda g: (
                    order[0] not in g,
                    sum(distance(a, b) for a, b in itertools.combinations(g, 2)),
                    [order.index(angle) for angle in g],
                ),
            )
            return [angle for angle in order if angle not in kept]
    return []


def evaluate_signatures(
    angles: Sequence[str], signatures: Mapping[str, Signature], threshold: float
) -> IdentityResult:
    """The same-person result for the current signatures of the required angles.

    Angles without a signature make the set ``incomplete`` (nothing is flagged). Signatures
    for angles that are not required are ignored.
    """
    if any(angle not in signatures for angle in angles):
        return IdentityResult(status="incomplete", mismatched_angles=())
    distances = {
        frozenset({a, b}): signature_distance(signatures[a], signatures[b])
        for a, b in itertools.combinations(angles, 2)
    }
    flagged = flag_mismatches(angles, distances, threshold)
    if not flagged:
        return IdentityResult(status="consistent", mismatched_angles=())
    return IdentityResult(status="mismatch", mismatched_angles=tuple(flagged))
