"""FastAPI dependencies for image routes."""

from __future__ import annotations

from fastapi import Request, Response

from app.images.service import ImageGenerationService


def get_images(request: Request) -> ImageGenerationService:
    """The image service wired by the app factory."""
    service: ImageGenerationService = request.app.state.images
    return service


def no_store(response: Response) -> None:
    """Images are personal: never let a browser or proxy cache the listing."""
    response.headers["Cache-Control"] = "no-store"
