"""MediaPipe Face Landmarker (478-point mesh) indices used by the measurements.

Names follow the person's own sides: ``R`` is the person's right (image left in a front
photo), ``L`` the person's left. The indices are from MediaPipe's canonical face mesh.
"""

from __future__ import annotations

from typing import Final

# --- Face outline and midline -------------------------------------------------------------
TOP: Final = 10  # top of the mesh forehead (the mesh stops below the hairline)
GLABELLA: Final = 9  # between the eyebrows
NASION: Final = 168
SUBNASALE: Final = 2  # base of the nose
CHIN_TIP: Final = 152
FACE_EDGE_R: Final = 234  # widest point of the face, person's right
FACE_EDGE_L: Final = 454
GONION_R: Final = 172  # jaw angle area
GONION_L: Final = 397
TEMPLE_R: Final = 54
TEMPLE_L: Final = 284
CHEEK_R: Final = 205
CHEEK_L: Final = 425
MIDLINE: Final = (TOP, NASION, SUBNASALE, CHIN_TIP)

# --- Eyes -----------------------------------------------------------------------------------
EYE_R_OUTER: Final = 33
EYE_R_INNER: Final = 133
EYE_R_TOP: Final = 159
EYE_R_BOTTOM: Final = 145
EYE_L_INNER: Final = 362
EYE_L_OUTER: Final = 263
EYE_L_TOP: Final = 386
EYE_L_BOTTOM: Final = 374

# --- Eyebrows -------------------------------------------------------------------------------
BROW_R_OUTER: Final = 70
BROW_R_PEAK: Final = 105
BROW_R_INNER: Final = 107
BROW_L_OUTER: Final = 300
BROW_L_PEAK: Final = 334
BROW_L_INNER: Final = 336

# --- Nose -----------------------------------------------------------------------------------
ALA_R: Final = 129
ALA_L: Final = 358

# --- Lips and chin --------------------------------------------------------------------------
MOUTH_R: Final = 61
MOUTH_L: Final = 291
UPPER_LIP_TOP: Final = 0
UPPER_LIP_BOTTOM: Final = 13
LOWER_LIP_TOP: Final = 14
LOWER_LIP_BOTTOM: Final = 17
CHIN_R: Final = 149
CHIN_L: Final = 378

#: Mirror pairs ``(right, left)`` by region, for the symmetry score (US7.5).
SYMMETRY_REGIONS: Final[dict[str, tuple[tuple[int, int], ...]]] = {
    "eyes": ((33, 263), (133, 362), (159, 386), (145, 374)),
    "brows": ((70, 300), (105, 334), (107, 336), (46, 276)),
    "nose": ((129, 358), (98, 327), (49, 279)),
    "mouth": ((61, 291), (37, 267), (84, 314)),
    "jaw_and_cheeks": ((234, 454), (172, 397), (205, 425), (58, 288), (132, 361)),
}
