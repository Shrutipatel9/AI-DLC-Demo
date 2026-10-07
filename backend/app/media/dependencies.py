"""FastAPI dependencies for media routes."""

from __future__ import annotations

from fastapi import Request

from app.media.services import MediaStore


def get_media_store(request: Request) -> MediaStore:
    """The MediaStore wired by the app factory."""
    store: MediaStore = request.app.state.media
    return store
