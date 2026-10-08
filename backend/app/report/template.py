"""The report's configured template text: versioned seed data (US8.2, US8.7; [RT] 4-6, 9.3, 10).

Standing, non-AI-generated copy. It is never produced by the text model, never shortened per
report and has no raw internal identifiers in it. Change a sentence by editing it here and
bumping ``TEMPLATE_VERSION``; a cached PDF built from an older version is rebuilt.

Items the specification marks TBD stay out: the data-retention window, the full privacy-policy
link, the exact AI-image disclosure wording and later treatment phases are the client's to
decide ([RD] 20, [RT] 19). Wording marked [Decided by delivery team] is ours.
"""

from __future__ import annotations

from typing import Final

TEMPLATE_VERSION: Final = "u8-v1"

#: The visible label on every AI image (same wording as the AI Visuals screen).
#: [Decided by delivery team] [RT] 19 item 2 leaves the exact wording open.
AI_IMAGE_LABEL: Final = "AI-generated illustration"

#: Plain feature names, in the report's order (BR-008).
FEATURE_TITLES: Final[dict[str, str]] = {
    "hair": "Hair",
    "eyebrows": "Eyebrows",
    "eyes": "Eyes",
    "nose": "Nose",
    "cheeks": "Cheeks",
    "jaw": "Jaw",
    "lips": "Lips",
    "chin": "Chin",
    "skin": "Skin",
    "neck": "Neck",
    "ears": "Ears",
}

#: [RT] 5: method and framing only; no finding, score, vendor or internal formula.
INTRODUCTION: Final = (
    "This report looks at your face feature by feature, using measurements taken from your "
    "own photos. Measuring makes the findings less subjective than a quick visual impression, "
    "and every number you see is shown alongside a plain-language explanation."
)

#: [RT] 5: what can affect accuracy, plus the restated "not a medical diagnosis" line.
LIMITATIONS: Final = (
    "Measurements can be affected by head position, lighting, camera quality and the lack of "
    "any radiographic imaging. Treat the numbers as a guide, not an exact result. This report "
    "is not a medical diagnosis."
)

#: [RT] 6 / [RD] 7: shown before the first score or feature (Q11).
UNDERSTANDING_INTRO: Final = "Please read these four points before you look at any results."
UNDERSTANDING_PRINCIPLES: Final[tuple[tuple[str, str], ...]] = (
    (
        "The recommendations focus on markers of facial health and harmony.",
        "They work with the features you already have rather than trying to change what makes "
        "you distinctive.",
    ),
    (
        "This platform does not rate attractiveness.",
        "The assessment highlights what works best for your own features using objective "
        "measurement, not a universal standard of beauty.",
    ),
    (
        "The protocol mixes foundational and targeted guidance.",
        "Fundamentals such as sun protection, sleep and hydration support the effect of the "
        "more specific suggestions; they are not filler.",
    ),
    (
        "All recommendations are informational and aesthetic only.",
        "Any in-clinic treatment or prescription product should be discussed with a qualified "
        "medical professional.",
    ),
)

#: US8.2: the static "consult a qualified professional" copy, exactly as configured.
PROFESSIONAL_ADVICE: Final = (
    "These recommendations are general and cosmetic. Please consult a qualified professional "
    "before starting any treatment, in-clinic procedure or prescription product."
)

#: [RT] 9.3 gives the over-the-counter example; the other two follow it [Decided by delivery team].
TIER_CAPTIONS: Final[dict[str, str]] = {
    "at_home": "This is a gentle, at-home recommendation.",
    "over_the_counter": "This is a non-invasive, over-the-counter-level recommendation.",
    "in_clinic": "This is an in-clinic option to discuss with a qualified professional.",
}
TIER_TITLES: Final[dict[str, str]] = {
    "at_home": "At home",
    "over_the_counter": "Over the counter",
    "in_clinic": "In clinic",
}

#: [RT] 4 (substance only; the retention window and policy link are TBD and left out).
DISCLAIMER_POINTS: Final[tuple[str, ...]] = (
    "This is an AI-assisted facial appearance analysis. It is informational and cosmetic.",
    "It is not a medical diagnosis, a clinical assessment, a surgical plan or a way to detect "
    "disease.",
    "Recommendations are general and cosmetic. They are not treatment.",
    "Numeric scores are not judgments of attractiveness or beauty.",
    "Any AI-generated before or after picture is an illustration with no guaranteed real-world "
    "outcome.",
)
PRIVACY_POINTS: Final[tuple[str, ...]] = (
    "Your photos and report are private to your account and are used only to produce this report.",
    "Images created by the platform are stored as whole images within your report.",
)

#: [RT] 10 Skin: a tiered at-home regimen, then longer-horizon habits [Decided by delivery team
#: for the wording; the structure is the specification's].
SKIN_SUBSECTIONS: Final[tuple[tuple[str, str], ...]] = (
    (
        "Skincare Protocol",
        "A simple at-home routine: a gentle cleanser, then a moisturiser, then sun protection "
        "every morning, then one targeted active ingredient added slowly.",
    ),
    (
        "Further Skin Enhancement",
        "Patch-test any new active ingredient before using it on your whole face, and "
        "introduce one new product at a time over several weeks.",
    ),
)

#: Plain descriptions of the first-pass face shapes ([RD] 9.2 face-shape view).
FACE_SHAPE_DESCRIPTIONS: Final[dict[str, str]] = {
    "oval": "Slightly longer than wide, with a softly rounded jaw and balanced widths.",
    "round": "About as wide as it is long, with soft curves and a rounded jaw.",
    "square": "A strong, angular jawline with forehead and jaw of similar width.",
    "heart": "A wider forehead that narrows toward a smaller jaw and chin.",
    "diamond": "Widest at the cheekbones, with a narrower forehead and jaw.",
    "oblong": "Noticeably longer than it is wide, with fairly even widths.",
}

#: Home protocol card ([RT] 3.7); a single Phase 01 is observed in the reference, later phases
#: are open ([RD] 14) and are left out.
PROTOCOL_PHASE_LABEL: Final = "PHASE 01"
PROTOCOL_PHASE_TITLE: Final = "Foundation and Everyday Care"
PROTOCOL_TIMING: Final = "Immediate to weeks 1-12"
PROTOCOL_CLOSING: Final = (
    "This phase comes first because everyday habits are low effort and support everything "
    "else. They are cosmetic guidance, not a treatment plan."
)

PDF_TITLE: Final = "Your Facial Analysis Report"
PDF_PROTOCOL_PARAGRAPHS: Final[tuple[str, ...]] = (
    "This protocol shows what you can do to move toward your own aesthetic potential. It never "
    "promises a specific outcome.",
    "The analysis is objective and non-comparative: it highlights your strengths and the "
    "areas with the most practical opportunity, rather than measuring you against an ideal.",
)
