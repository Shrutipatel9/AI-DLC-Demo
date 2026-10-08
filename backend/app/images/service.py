"""ImageGeneration use cases: the pipeline step, reading the slots and the manual retry.

Rules (US9.1-US9.5):
- The step replaces U6's placeholder: it generates the missing slots with the configured
  concurrency; a slot that fails after its automatic attempts is "not available yet" and the
  report still publishes (AC9.5.2). The narratives were saved by the earlier step, so they are
  already readable while images generate (AC9.5.5).
- Every image is private to the run's owner; another user gets 404 (AC9.1.3).
- A manual retry is one vendor attempt, at most ``manual_limit`` per slot; past the limit it is
  refused without a vendor call (AC9.5.4).
"""

from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.public import ImageInput
from app.analysis.public import (
    SLOT_KINDS,
    RunContext,
    RunRef,
    SlotView,
    StepResult,
    claim_manual_retry,
    ensure_slots,
    find_slot_view,
    latest_run_ref,
    list_slot_views,
    record_auto_result,
    record_manual_result,
)
from app.images.catalog import CATALOG, PromptSpec, order_of, spec_for
from app.images.generator import SlotGenerator
from app.media.public import MediaStore, StorageError
from app.platform.clock import Clock
from app.platform.db import SessionFactory
from app.platform.errors import ImageRetryNotAvailable, NotFound

logger = logging.getLogger("images")

FRONT = "front"
PHOTO_FAILURE = "A photo from the analysis could not be read."

#: Slot states on the wire.
GENERATING = "generating"
READY = "ready"
NOT_AVAILABLE = "not_available"


@dataclass(frozen=True)
class SlotState:
    """One slot as the AI Visuals screen needs it."""

    slot_id: str
    group: str
    title: str
    state: str
    file_id: uuid.UUID | None
    retries_left: int


@dataclass(frozen=True)
class ImagesState:
    """The run's images."""

    run_id: uuid.UUID
    generating: bool
    front_file_id: uuid.UUID | None
    slots: tuple[SlotState, ...]


class ImageGenerationService:
    """Generates and serves the images.

    Args:
        generator: Makes one image.
        media: Private storage (reads the front photo).
        session_factory: Short sessions for the worker-side step.
        clock: Time source.
        concurrency: Images generated at once (AC7.6.4).
        manual_limit: Manual retries per slot (AC9.5.4).
    """

    def __init__(
        self,
        *,
        generator: SlotGenerator,
        media: MediaStore,
        session_factory: SessionFactory,
        clock: Clock,
        concurrency: int,
        manual_limit: int,
    ) -> None:
        self.generator = generator
        self.media = media
        self.session_factory = session_factory
        self.clock = clock
        self.concurrency = concurrency
        self.manual_limit = manual_limit

    # --- Pipeline step ------------------------------------------------------------------------

    def generate_step(self, ctx: RunContext) -> StepResult:
        """The ``generating_images`` step (US9.1, US9.5); idempotent, resumes pending slots."""
        front_id = ctx.photo_snapshot.get(FRONT)
        if front_id is None:
            return StepResult("failed", PHOTO_FAILURE)
        try:
            with ctx.session_factory() as session:
                source = self._source(session, front_id, ctx.user_id)
        except (NotFound, StorageError):
            return StepResult("failed", PHOTO_FAILURE)
        with ctx.session_factory() as session:
            ensure_slots(session, ctx.run_id, dict(SLOT_KINDS))
            session.commit()
            pending = [
                view.slot_key
                for view in list_slot_views(session, ctx.run_id)
                if view.status == "pending"
            ]

        def work(slot_key: str) -> bool:
            spec = spec_for(slot_key)
            if spec is None:  # a slot the catalog does not know: never retried
                file_id, calls = None, 0
            else:
                file_id, calls = self.generator.generate(ctx.user_id, source, spec)
            with ctx.session_factory() as session:
                record_auto_result(
                    session,
                    ctx.run_id,
                    slot_key,
                    media_file_id=file_id,
                    attempts=calls,
                    now=self.clock.now(),
                )
                session.commit()
            return file_id is not None

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            ready = sum(pool.map(work, pending))
        logger.info(
            "images generated",
            extra={"event": "images.generated", "ready": ready, "pending": len(pending)},
        )
        return StepResult("done", output={"slots": len(CATALOG), "ready": ready})

    # --- Reading ------------------------------------------------------------------------------

    def state_for(self, session: Session, user_id: uuid.UUID) -> ImagesState:
        """The user's newest run's images.

        Raises:
            NotFound: When the user has no run.
        """
        run = latest_run_ref(session, user_id)
        if run is None:
            raise NotFound("We couldn't find your images.")
        views = sorted(list_slot_views(session, run.run_id), key=lambda v: order_of(v.slot_key))
        slots = tuple(self._state(view) for view in views if spec_for(view.slot_key) is not None)
        generating = run.status == "running" or any(slot.state == GENERATING for slot in slots)
        return ImagesState(run.run_id, generating, run.photo_snapshot.get(FRONT), slots)

    def _state(self, view: SlotView) -> SlotState:
        spec = spec_for(view.slot_key)
        assert spec is not None  # noqa: S101  (callers filter unknown keys)
        if view.status == "ready" and view.media_file_id is not None:
            state = READY
        elif view.status == "pending":
            state = GENERATING
        else:
            state = NOT_AVAILABLE
        return SlotState(
            slot_id=view.slot_key,
            group=spec.group,
            title=spec.title,
            state=state,
            file_id=view.media_file_id if state == READY else None,
            retries_left=max(self.manual_limit - view.manual_retries, 0),
        )

    # --- Manual retry -------------------------------------------------------------------------

    def retry(self, session: Session, user_id: uuid.UUID, slot_id: str) -> SlotState:
        """Retry one "not available yet" image once (AC9.5.3); commits its own work.

        Raises:
            NotFound: No such slot in the user's run (another user's slot looks the same).
            ImageRetryNotAvailable: Not marked "not available yet", or the retries are used up;
                no vendor call is made.
        """
        run = latest_run_ref(session, user_id)
        spec = spec_for(slot_id)
        if run is None or spec is None or find_slot_view(session, run.run_id, slot_id) is None:
            raise NotFound("We couldn't find that image.")
        claimed = claim_manual_retry(
            session, run.run_id, slot_id, limit=self.manual_limit, now=self.clock.now()
        )
        session.commit()
        if not claimed:
            raise ImageRetryNotAvailable()
        file_id = self._manual_attempt(session, run, spec)
        record_manual_result(
            session, run.run_id, slot_id, media_file_id=file_id, now=self.clock.now()
        )
        session.commit()
        view = find_slot_view(session, run.run_id, slot_id)
        assert view is not None  # noqa: S101  (it was just updated)
        return self._state(view)

    def _manual_attempt(self, session: Session, run: RunRef, spec: PromptSpec) -> uuid.UUID | None:
        front_id = run.photo_snapshot.get(FRONT)
        try:
            if front_id is None:
                raise NotFound(PHOTO_FAILURE)
            source = self._source(session, front_id, run.user_id)
            return self.generator.attempt(run.user_id, source, spec)
        except Exception as error:  # a failed retry only leaves the slot marked (AC9.5.3)
            logger.warning(
                "manual image retry failed",
                extra={
                    "event": "images.retry_failed",
                    "slot": spec.slot_key,
                    "errorClass": type(error).__name__,
                },
            )
            return None

    def _source(self, session: Session, front_id: uuid.UUID, user_id: uuid.UUID) -> ImageInput:
        stored = self.media.get(session, front_id, user_id)
        return ImageInput(stored.data, stored.content_type, FRONT)
