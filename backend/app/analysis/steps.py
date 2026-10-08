"""The built-in pipeline steps (contract C7 providers).

Measuring, writing, the image slots and assembling.

Short database sessions only; the CPU and vendor work happens outside any transaction
(NFR5.13). Photos are read through the MediaStore with the run's verified owner, from the
snapshot recorded when the run started (R-02).
"""

from __future__ import annotations

import logging
from typing import Any

from app.ai.public import ImageInput
from app.analysis import repositories
from app.analysis.domain import (
    FRONT_ANGLE,
    STEP_ASSEMBLING,
    STEP_GENERATING_IMAGES,
    STEP_MEASURING,
    STEP_WRITING,
)
from app.analysis.models import AnalysisImageSlot, SlotStatus
from app.analysis.pipeline import AnalysisPipeline, RunContext, StepResult
from app.face.public import RgbImage
from app.measurement.public import (
    EAR_ANGLES,
    FEATURE_KEYS,
    MeasurementError,
    MeasurementService,
)
from app.media.public import MediaStore, UnreadableImageError, decode_stored
from app.onboarding.public import OnboardingService, get_non_medical_answers, needs_reassurance
from app.platform.clock import Clock
from app.platform.errors import NotFound
from app.report_writing.public import AnswerForAi, ReportWritingFailed, ReportWritingService

logger = logging.getLogger("analysis")

#: The 24 image slots (FR-020, FR-022): 11 feature "after" images, 5 hairstyles, 5 outfits and
#: the 3 generated healthy-aging cards (the 4th card is the user's own photo).
SLOT_KINDS: tuple[tuple[str, str], ...] = (
    *((key, "feature_after") for key in FEATURE_KEYS),
    *((f"hairstyle_{n}", "hairstyle") for n in range(1, 6)),
    *((f"outfit_{n}", "outfit") for n in range(1, 6)),
    ("aging_plus_3", "aging"),
    ("aging_plus_5", "aging"),
    ("aging_plus_10", "aging"),
)
SLOT_COUNT = len(SLOT_KINDS)

MEASURE_FAILURE = "Your photos could not be measured."
WRITE_FAILURE = "The report text could not be written."
PHOTO_FAILURE = "A photo from the analysis could not be read."


class AnalysisSteps:
    """The step handlers, with their collaborators.

    Args:
        media: Private photo storage.
        measurement: FaceMeasurement.
        onboarding: Onboarding (non-medical answers and the tone rule).
        report_writing: ReportWriting.
        clock: Time source.
        distress_trigger: ``TONE_DISTRESS_TRIGGER``.
        frequency_trigger: ``TONE_FREQUENCY_TRIGGER``.
    """

    def __init__(
        self,
        *,
        media: MediaStore,
        measurement: MeasurementService,
        onboarding: OnboardingService,
        report_writing: ReportWritingService,
        clock: Clock,
        distress_trigger: str,
        frequency_trigger: str,
    ) -> None:
        self.media = media
        self.measurement = measurement
        self.onboarding = onboarding
        self.report_writing = report_writing
        self.clock = clock
        self.distress_trigger = distress_trigger
        self.frequency_trigger = frequency_trigger

    def register(self, pipeline: AnalysisPipeline) -> None:
        """Register the four steps in order."""
        pipeline.register_step(STEP_MEASURING, 10, self.measuring)
        pipeline.register_step(STEP_WRITING, 20, self.writing)
        pipeline.register_step(STEP_GENERATING_IMAGES, 30, self.generating_images)
        pipeline.register_step(STEP_ASSEMBLING, 40, self.assembling)

    # --- Photos -------------------------------------------------------------------------------

    def _photo(self, ctx: RunContext, angle: str) -> tuple[bytes, str] | None:
        file_id = ctx.photo_snapshot.get(angle)
        if file_id is None:
            return None
        with ctx.session_factory() as session:
            stored = self.media.get(session, file_id, ctx.user_id)
        return stored.data, stored.content_type

    # --- Steps --------------------------------------------------------------------------------

    def measuring(self, ctx: RunContext) -> StepResult:
        """Measurements and assessments from the run's photos (US7.3-US7.10)."""
        try:
            front = self._photo(ctx, FRONT_ANGLE)
            if front is None:
                return StepResult("failed", MEASURE_FAILURE)
            sides: dict[str, RgbImage | None] = {}
            for angle in EAR_ANGLES.values():
                photo = self._photo(ctx, angle)
                sides[angle] = None if photo is None else decode_stored(photo[0])
            result = self.measurement.measure(decode_stored(front[0]), sides)
        except (NotFound, UnreadableImageError):
            return StepResult("failed", PHOTO_FAILURE)
        except MeasurementError:
            return StepResult("failed", MEASURE_FAILURE)
        return StepResult("done", output={"measurements": result})

    def writing(self, ctx: RunContext) -> StepResult:
        """The report text for all 11 features (US7.4, US7.9)."""
        measurements = ctx.outputs[STEP_MEASURING]["measurements"]
        photos: list[ImageInput] = []
        try:
            for angle, file_id in ctx.photo_snapshot.items():
                with ctx.session_factory() as session:
                    stored = self.media.get(session, file_id, ctx.user_id)
                photos.append(ImageInput(stored.data, stored.content_type, angle))
        except NotFound:
            return StepResult("failed", PHOTO_FAILURE)
        with ctx.session_factory() as session:
            answers = [
                AnswerForAi(answer.question_text, answer.answer_text)
                for answer in get_non_medical_answers(self.onboarding, session, ctx.user_id)
            ]
            reassure = needs_reassurance(
                self.onboarding,
                session,
                ctx.user_id,
                distress_at=self.distress_trigger,
                frequency_at=self.frequency_trigger,
            )
        try:
            text = self.report_writing.write(
                answers=answers, measurements=measurements, photos=photos, reassure=reassure
            )
        except ReportWritingFailed:
            return StepResult("failed", WRITE_FAILURE)
        return StepResult("done", output={"reportText": text})

    def generating_images(self, ctx: RunContext) -> StepResult:
        """Record the 24 slots as "not available yet"; U7 generates the images."""
        with ctx.session_factory() as session:
            if not repositories.list_slots(session, ctx.run_id):
                repositories.add_slots(
                    session,
                    (
                        AnalysisImageSlot(
                            run_id=ctx.run_id,
                            slot_key=key,
                            slot_kind=kind,
                            status=SlotStatus.NOT_AVAILABLE_YET.value,
                        )
                        for key, kind in SLOT_KINDS
                    ),
                )
                session.commit()
        return StepResult("done", output={"slots": SLOT_COUNT})

    def assembling(self, ctx: RunContext) -> StepResult:
        """Store the analysis result (AC7.9.3); U8 publishes the report from it."""
        result: dict[str, Any] = {
            "measurements": ctx.outputs[STEP_MEASURING]["measurements"],
            "reportText": ctx.outputs[STEP_WRITING]["reportText"],
            "imageSlots": SLOT_COUNT,
        }
        with ctx.session_factory() as session:
            if repositories.find_result(session, ctx.run_id) is None:
                repositories.add_result(session, ctx.run_id, ctx.user_id, result, self.clock.now())
                session.commit()
        return StepResult("done")
