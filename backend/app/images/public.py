"""The ImageGeneration module's public interface. Other modules import only this.

- ``build_image_generation``: the service from settings (vendor adapter chosen by
  ``AI_IMAGE_PROVIDER``; both the API and the worker build one).
- ``register_image_step``: puts the generation step into the analysis pipeline in place of
  U6's placeholder (contract C7).
- ``router``: ``/images`` (mounted as protected routes).
"""

from __future__ import annotations

import time

from app.ai.public import ImageEditor, build_image_editor
from app.analysis.public import STEP_GENERATING_IMAGES, AnalysisPipeline
from app.images.generator import Sleeper, SlotGenerator
from app.images.routes import router
from app.images.service import ImageGenerationService
from app.media.public import MediaStore
from app.platform.clock import Clock
from app.platform.db import SessionFactory
from app.platform.settings import Settings

__all__ = [
    "ImageGenerationService",
    "build_image_generation",
    "register_image_step",
    "router",
]

#: Where the step sits among the pipeline's steps (after writing, before assembling).
IMAGE_STEP_ORDER = 30


def build_image_generation(
    settings: Settings,
    *,
    clock: Clock,
    session_factory: SessionFactory,
    media: MediaStore,
    editor: ImageEditor | None = None,
    sleep: Sleeper = time.sleep,
) -> ImageGenerationService:
    """Create the image service; ``editor`` overrides the configured adapter (tests)."""
    generator = SlotGenerator(
        editor=editor or build_image_editor(settings),
        media=media,
        session_factory=session_factory,
        fidelity=settings.ai_image_fidelity,
        auto_retries=settings.ai_image_auto_retries,
        backoff_seconds=settings.ai_retry_backoff_seconds,
        sleep=sleep,
    )
    return ImageGenerationService(
        generator=generator,
        media=media,
        session_factory=session_factory,
        clock=clock,
        concurrency=settings.ai_image_concurrency,
        manual_limit=settings.ai_image_manual_retry_limit,
    )


def register_image_step(pipeline: AnalysisPipeline, service: ImageGenerationService) -> None:
    """Replace the placeholder ``generating_images`` step with the real one."""
    pipeline.register_step(STEP_GENERATING_IMAGES, IMAGE_STEP_ORDER, service.generate_step)
