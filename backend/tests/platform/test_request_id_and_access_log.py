"""Request id and access log (NFR5.6, NFR5.7, NFR5.10)."""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from app.platform.metrics import Metrics
from app.platform.request_id import accept_or_generate, get_request_id


def test_canonical_uuid_is_accepted_and_lowercased(platform_client: TestClient) -> None:
    incoming = str(uuid.uuid4()).upper()
    response = platform_client.get("/items/1", headers={"X-Request-ID": incoming})
    assert response.headers["X-Request-ID"] == incoming.lower()


@pytest.mark.parametrize(
    "bad", ["abc", "x" * 36, "12345678-1234-1234-1234-1234567890ab\nINJECT", ""]
)
def test_malformed_request_id_is_replaced(bad: str) -> None:
    replaced = accept_or_generate(bad)
    assert replaced != bad
    assert uuid.UUID(replaced).version == 4


def test_every_response_gets_a_request_id(platform_client: TestClient) -> None:
    first = platform_client.get("/items/1").headers["X-Request-ID"]
    second = platform_client.get("/items/1").headers["X-Request-ID"]
    assert first != second
    uuid.UUID(first)
    # Outside a request a fresh id is generated rather than failing.
    uuid.UUID(get_request_id())


def test_access_log_uses_route_template_and_unmatched_label(
    platform_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="http.access")
    platform_client.get("/items/42")
    platform_client.get("/does/not/exist/12345")
    lines = [r for r in caplog.records if getattr(r, "event", None) == "http.request"]
    routes = [r.__dict__["route"] for r in lines]
    assert "/items/{item_id}" in routes
    assert "unmatched" in routes
    assert all("12345" not in route and "42" not in route for route in routes)
    matched = next(r for r in lines if r.__dict__["route"] == "/items/{item_id}")
    assert matched.__dict__["status"] == 200
    assert matched.__dict__["method"] == "GET"
    assert matched.__dict__["durationMs"] >= 0


def test_access_middleware_records_red_metrics(
    platform_client: TestClient, platform_metrics: Metrics
) -> None:
    platform_client.get("/items/7")
    platform_client.get("/items/0")
    exposition = platform_metrics.render().decode()
    assert (
        'http_requests_total{method="GET",route="/items/{item_id}",status="200"} 1.0' in exposition
    )
    assert (
        'http_requests_total{method="GET",route="/items/{item_id}",status="404"} 1.0' in exposition
    )
    assert "http_request_duration_seconds_bucket" in exposition
