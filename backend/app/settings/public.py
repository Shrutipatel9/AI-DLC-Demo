"""The Settings module's public interface: its router (mounted as protected routes)."""

from __future__ import annotations

from app.settings.routes import router

__all__ = ["router"]
