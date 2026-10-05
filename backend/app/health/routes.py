"""Liveness and readiness probes (NFR5.5, reliability design section 4).

Both are ``async def``, so they never wait for a thread-pool slot behind slow work.
Readiness runs ``SELECT 1`` in a thread with a 2-second limit and returns no details.
"""

from __future__ import annotations

import logging
from typing import Literal

import anyio
import anyio.to_thread
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.platform.db import ping

logger = logging.getLogger("health")

READINESS_TIMEOUT_SECONDS = 2.0

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    """Probe body; never carries details."""

    status: Literal["ok", "unavailable"]


@router.get("/health", summary="Liveness check", response_model=HealthStatus)
async def health() -> HealthStatus:
    """The process is serving. No I/O."""
    return HealthStatus(status="ok")


@router.get(
    "/health/ready",
    summary="Readiness check (database reachable)",
    response_model=HealthStatus,
    responses={503: {"model": HealthStatus, "description": "Database not reachable"}},
)
async def ready(request: Request) -> JSONResponse:
    """200 when the database answers within 2 seconds, otherwise 503 (no details)."""
    factory = request.app.state.session_factory
    try:
        with anyio.fail_after(READINESS_TIMEOUT_SECONDS):
            await anyio.to_thread.run_sync(ping, factory, abandon_on_cancel=True)
    except Exception:
        logger.warning("readiness check failed", exc_info=True, extra={"event": "health.not_ready"})
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(status_code=200, content={"status": "ok"})
