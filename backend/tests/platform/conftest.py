"""A minimal app with the real middleware stack and error handlers, for platform tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.platform.errors import CodeLocked, NotFound, install_exception_handlers
from app.platform.metrics import Metrics
from app.platform.middleware import install_middleware
from app.platform.settings import Settings
from tests.helpers import make_settings


class Echo(BaseModel):
    """Body used to exercise validation errors."""

    name: str = Field(min_length=1, max_length=5)


def build_platform_app(settings: Settings, metrics: Metrics | None = None) -> FastAPI:
    """FastAPI app with platform middleware, handlers and a few probe routes."""
    app = FastAPI()
    install_exception_handlers(app)
    install_middleware(app, settings, metrics)

    @app.get("/items/{item_id}")
    def read_item(item_id: int) -> dict[str, int]:
        if item_id == 0:
            raise NotFound()
        return {"id": item_id}

    @app.post("/auth/echo")
    async def echo(body: Echo) -> dict[str, str]:
        return {"name": body.name}

    @app.post("/auth/raw")
    async def raw(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @app.get("/auth/locked")
    def locked() -> None:
        raise CodeLocked(retry_after=120)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    return app


@pytest.fixture
def platform_metrics() -> Metrics:
    """Fresh metrics registry."""
    return Metrics()


@pytest.fixture
def platform_client(platform_metrics: Metrics) -> Iterator[TestClient]:
    """Client for the probe app in APP_ENV=test (HSTS on)."""
    app = build_platform_app(make_settings(), platform_metrics)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
