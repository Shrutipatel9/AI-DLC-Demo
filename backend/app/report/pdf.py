"""The report PDF, rendered on the server from a template this module owns (R-01, US8.5).

The page order follows [RD] 5-10: Disclaimer and Privacy, Introduction (with Limitations and
Contents), Understanding the Results, the Protocol overview, then the Facial Assessments (the
first page with a score, so the preamble always comes first, AC8.7.2), one page per feature in
the report's order, and the Closing Recommendations. It is built only from the published report
and the stored images; it never calls the network or a model.

[Decided by delivery team] Page numbers start at 1, each feature has its own page, and the
Closing Recommendations page lists the tiered recommendations instead of a written synthesis.
The built-in PDF fonts only cover Latin-1, so a character outside it is replaced.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Final

from fpdf import FPDF
from PIL import Image

from app.report import template
from app.report.schemas import FeatureOut, ReportOut

PAGE_WIDTH: Final = 210.0
MARGIN: Final = 18.0
CONTENT_WIDTH: Final = PAGE_WIDTH - 2 * MARGIN
IMAGE_MAX_SIDE: Final = 480
IMAGE_QUALITY: Final = 80
PHOTO_WIDTH_MM: Final = 70.0
PHOTO_MAX_HEIGHT_MM: Final = 80.0

ACCENT = (24, 120, 110)
MUTED = (110, 110, 110)
CALLOUT_FILL = (236, 244, 243)

SECTION_DISCLAIMER: Final = "Disclaimer and Privacy"
SECTION_INTRODUCTION: Final = "Introduction"
SECTION_UNDERSTANDING: Final = "Understanding the Results"
SECTION_PROTOCOL: Final = "Your Protocol"
SECTION_ASSESSMENTS: Final = "Facial Assessments"
SECTION_CLOSING: Final = "Closing Recommendations"

_REPLACEMENTS: Final = {
    "—": "-",
    "–": "-",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "…": "...",
    "→": "->",
}


@dataclass(frozen=True)
class PdfImage:
    """A stored picture prepared for the PDF."""

    data: bytes
    width: int
    height: int


def prepare_image(data: bytes) -> PdfImage | None:
    """Shrink and re-encode a stored picture to a small JPEG, or ``None`` when unreadable."""
    try:
        with Image.open(io.BytesIO(data)) as source:
            picture = source.convert("RGB")
    except (OSError, ValueError):
        return None
    picture.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE))
    buffer = io.BytesIO()
    picture.save(buffer, format="JPEG", quality=IMAGE_QUALITY)
    return PdfImage(buffer.getvalue(), picture.width, picture.height)


def clean(text: str) -> str:
    """Text the built-in PDF fonts can draw (Latin-1)."""
    for char, replacement in _REPLACEMENTS.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", "replace").decode("latin-1")


class _Pdf(FPDF):
    """The page frame: a thin accent rule, the title and the page number."""

    def header(self) -> None:
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.8)
        self.line(MARGIN, 12, PAGE_WIDTH - MARGIN, 12)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, clean(f"{template.PDF_TITLE}   |   PAGE {self.page_no()}"), align="C")
        self.set_text_color(0, 0, 0)


class _Writer:
    """Drawing helpers that keep every page tidy."""

    def __init__(self) -> None:
        self.pdf = _Pdf(format="A4", unit="mm")
        self.pdf.set_margins(MARGIN, 18, MARGIN)
        self.pdf.set_auto_page_break(auto=True, margin=18)
        self.pdf.set_title(template.PDF_TITLE)
        self.pdf.set_creator("FaceIQ")
        self.pages: dict[str, int] = {}

    def section(self, name: str, subtitle: str = "") -> None:
        self.pdf.add_page()
        self.pages[name] = self.pdf.page_no()
        self.pdf.set_font("helvetica", "B", 20)
        self.pdf.set_text_color(*ACCENT)
        self._line(name, 10)
        if subtitle:
            self.pdf.set_font("helvetica", "", 11)
            self.pdf.set_text_color(*MUTED)
            self._line(subtitle, 6)
        self.pdf.set_text_color(0, 0, 0)
        self.pdf.ln(3)

    def _line(self, text: str, height: float) -> None:
        self.pdf.multi_cell(0, height, clean(text), new_x="LMARGIN", new_y="NEXT")

    def heading(self, text: str) -> None:
        self.pdf.ln(2)
        self.pdf.set_font("helvetica", "B", 13)
        self._line(text, 7)

    def paragraph(self, text: str, *, bold: bool = False, muted: bool = False) -> None:
        self.pdf.set_font("helvetica", "B" if bold else "", 10.5)
        self.pdf.set_text_color(*(MUTED if muted else (0, 0, 0)))
        self._line(text, 5.5)
        self.pdf.set_text_color(0, 0, 0)
        self.pdf.ln(1.5)

    def bullets(self, items: list[str]) -> None:
        self.pdf.set_font("helvetica", "", 10.5)
        for item in items:
            self.pdf.set_x(MARGIN + 3)
            self.pdf.multi_cell(
                CONTENT_WIDTH - 3, 5.5, clean(f"- {item}"), new_x="LMARGIN", new_y="NEXT"
            )
        self.pdf.ln(1.5)

    def callout(self, title: str, body: str) -> None:
        self.pdf.ln(2)
        self.pdf.set_fill_color(*CALLOUT_FILL)
        self.pdf.set_font("helvetica", "B", 11)
        self.pdf.multi_cell(
            0, 6.5, clean(title), fill=True, new_x="LMARGIN", new_y="NEXT", padding=(1, 2, 0, 2)
        )
        self.pdf.set_font("helvetica", "", 10.5)
        self.pdf.multi_cell(
            0, 5.5, clean(body), fill=True, new_x="LMARGIN", new_y="NEXT", padding=(0, 2, 2, 2)
        )
        self.pdf.ln(2)

    def table(
        self, headers: tuple[str, ...], rows: list[tuple[str, ...]], widths: tuple[float, ...]
    ) -> None:
        self.pdf.set_font("helvetica", "B", 10)
        for header, width in zip(headers, widths, strict=True):
            self.pdf.cell(width, 6.5, clean(header), border="B")
        self.pdf.ln()
        self.pdf.set_font("helvetica", "", 10)
        for row in rows:
            for value, width in zip(row, widths, strict=True):
                self.pdf.cell(width, 6, clean(value))
            self.pdf.ln()
        self.pdf.ln(2)

    # --- Pictures -----------------------------------------------------------------------------

    def _fit(self, image: PdfImage) -> tuple[float, float]:
        width = PHOTO_WIDTH_MM
        height = width * image.height / image.width
        if height > PHOTO_MAX_HEIGHT_MM:
            width, height = width * PHOTO_MAX_HEIGHT_MM / height, PHOTO_MAX_HEIGHT_MM
        return width, height

    def photo_pair(
        self,
        before: PdfImage | None,
        after: PdfImage | None,
        *,
        after_note: str,
        title: str,
    ) -> None:
        """Before and after side by side, each with a chip; the after image carries its AI label."""
        sizes = [self._fit(image) for image in (before, after) if image is not None]
        needed = (max(h for _, h in sizes) if sizes else 12.0) + 14.0
        if self.pdf.get_y() + needed > self.pdf.page_break_trigger:
            self.pdf.add_page()
        top = self.pdf.get_y()
        tallest = 12.0
        for column, (label, image) in enumerate((("BEFORE", before), ("AFTER", after))):
            left = MARGIN + column * (PHOTO_WIDTH_MM + 8)
            if image is None:
                self.pdf.set_xy(left, top + 4)
                self.pdf.set_font("helvetica", "I", 10)
                self.pdf.set_text_color(*MUTED)
                note = after_note if label == "AFTER" else "Photo not available."
                self.pdf.multi_cell(PHOTO_WIDTH_MM, 5.5, clean(note))
                self.pdf.set_text_color(0, 0, 0)
                continue
            width, height = self._fit(image)
            self.pdf.image(
                io.BytesIO(image.data), x=left, y=top, w=width, h=height, alt_text=clean(title)
            )
            self.pdf.set_fill_color(40, 40, 40)
            self.pdf.set_text_color(255, 255, 255)
            self.pdf.set_font("helvetica", "B", 7)
            self.pdf.set_xy(left, top)
            self.pdf.cell(14, 4.5, label, fill=True, align="C")
            self.pdf.set_text_color(0, 0, 0)
            caption = template.AI_IMAGE_LABEL if label == "AFTER" else "Your photo"
            self.pdf.set_xy(left, top + height + 1)
            self.pdf.set_font("helvetica", "I", 8)
            self.pdf.cell(width, 4, clean(caption))
            tallest = max(tallest, height + 6)
        self.pdf.set_xy(MARGIN, top + tallest + 2)


def _feature_page(
    writer: _Writer, feature: FeatureOut, front: PdfImage | None, after: PdfImage | None
) -> None:
    writer.section(feature.title, "Recommendations")
    writer.paragraph(feature.narrative)
    writer.photo_pair(
        front,
        after,
        after_note="The AI illustration is not available yet.",
        title=feature.after.alt,
    )
    if feature.potential_ideas:
        writer.heading("Projected potential")
        writer.bullets(feature.potential_ideas)
    writer.heading("Measurements")
    if feature.metrics:
        writer.table(
            ("Measurement", "Value", "Unit"),
            [(m.label, f"{m.value:g}", m.unit) for m in feature.metrics],
            (100.0, 30.0, 40.0),
        )
    else:
        writer.paragraph(
            feature.no_measurement_reason or "No measurement is available.", muted=True
        )
    for sub in feature.sub_sections:
        writer.heading(sub.heading)
        writer.paragraph(sub.body)
    if feature.summary:
        writer.callout(f"{feature.title} Summary", feature.summary)


def _assessments_page(writer: _Writer, report: ReportOut) -> None:
    writer.section(SECTION_ASSESSMENTS)
    assessments = report.assessments
    if assessments.symmetry:
        symmetry = assessments.symmetry
        writer.heading("Symmetry")
        writer.paragraph(f"Score {symmetry.score} out of 100 - {symmetry.label}")
        writer.table(
            ("Region", "Score"),
            [(r.region.capitalize(), str(r.score)) for r in symmetry.regional_balance],
            (100.0, 40.0),
        )
    if assessments.facial_thirds:
        thirds = assessments.facial_thirds
        writer.heading("Facial thirds")
        writer.table(
            ("Third", "Share of face height"),
            [
                ("Upper", f"{thirds.upper * 100:.0f}%"),
                ("Middle", f"{thirds.middle * 100:.0f}%"),
                ("Lower", f"{thirds.lower * 100:.0f}%"),
            ],
            (100.0, 60.0),
        )
    if assessments.dimorphism:
        dimorphism = assessments.dimorphism
        writer.heading("Masculine and feminine balance")
        writer.paragraph(
            f"Masculine {dimorphism.masculinity:.0f}, feminine {dimorphism.femininity:.0f} - "
            f"{dimorphism.label}."
        )
    if assessments.prototypicality is not None:
        writer.heading("Prototypicality")
        writer.paragraph(f"{assessments.prototypicality:.0f} out of 100.")
    if assessments.face_shape:
        writer.heading("Face shape")
        writer.paragraph(
            f"{assessments.face_shape.name.capitalize()}. {assessments.face_shape.description}"
        )


def _closing_page(writer: _Writer, report: ReportOut) -> None:
    writer.section(SECTION_CLOSING)
    recommendations = report.recommendations
    tiers = (
        ("at_home", recommendations.at_home),
        ("over_the_counter", recommendations.over_the_counter),
        ("in_clinic", recommendations.in_clinic),
    )
    for tier, items in tiers:
        if not items:
            continue
        writer.heading(template.TIER_TITLES[tier])
        writer.paragraph(recommendations.tier_captions[tier], muted=True)
        writer.bullets([f"{item.feature_title}: {item.text}" for item in items])
    writer.paragraph(recommendations.professional_advice_text, bold=True)


def _build(
    report: ReportOut,
    front: PdfImage | None,
    afters: dict[str, PdfImage],
    contents: dict[str, int],
) -> _Writer:
    writer = _Writer()
    sections = report.template_sections

    writer.section(SECTION_DISCLAIMER)
    writer.heading("Disclaimer")
    writer.bullets(sections.disclaimer_points)
    writer.heading("Privacy")
    writer.bullets(sections.privacy_points)

    writer.section(SECTION_INTRODUCTION)
    writer.paragraph(sections.introduction)
    writer.heading("Limitations")
    writer.paragraph(sections.limitations)
    writer.heading("Contents")
    for name, page in contents.items():
        writer.pdf.set_font("helvetica", "", 10.5)
        writer.pdf.cell(CONTENT_WIDTH - 20, 6, clean(name))
        writer.pdf.cell(20, 6, str(page), align="R", new_x="LMARGIN", new_y="NEXT")

    understanding = sections.understanding_your_results
    writer.section(SECTION_UNDERSTANDING)
    writer.paragraph(understanding.intro, muted=True)
    for number, principle in enumerate(understanding.principles, start=1):
        writer.heading(f"{number:02d}  {principle.title}")
        writer.paragraph(principle.text)

    writer.section(SECTION_PROTOCOL)
    first = report.features[0]
    writer.photo_pair(
        front,
        afters.get(first.key),
        after_note="The AI illustration is not available yet.",
        title=first.after.alt,
    )
    for paragraph in template.PDF_PROTOCOL_PARAGRAPHS:
        writer.paragraph(paragraph)
    writer.heading("Projected potential")
    writer.bullets([feature.title for feature in report.features])

    _assessments_page(writer, report)
    for feature in report.features:
        _feature_page(writer, feature, front, afters.get(feature.key))
    _closing_page(writer, report)
    return writer


def render_pdf(
    report: ReportOut, front: PdfImage | None, afters: dict[str, PdfImage]
) -> tuple[bytes, dict[str, int]]:
    """The PDF bytes and the page each section starts on.

    Built twice: the first pass finds the page numbers the Contents list shows (it has the
    same length either way, so the second pass is exact).
    """
    first = _build(report, front, afters, {})
    contents = {
        name: page
        for name, page in first.pages.items()
        if name not in (SECTION_DISCLAIMER, SECTION_INTRODUCTION)
    }
    final = _build(report, front, afters, contents)
    return bytes(final.pdf.output()), final.pages
