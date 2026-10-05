"""Metrics series and the /metrics CIDR guard (NFR5.10, NFR2.8)."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from app.platform.metrics import Metrics, MetricsEndpoint


def _client(metrics: Metrics, cidrs: list[str]) -> TestClient:
    app = Starlette(routes=[Mount("/metrics", app=MetricsEndpoint(metrics, cidrs))])
    return TestClient(app)  # TestClient's peer address is "testclient"


def test_named_series_are_exposed() -> None:
    metrics = Metrics()
    metrics.auth_codes_sent_total.labels(purpose="signup").inc()
    metrics.observe_request("/auth/me", "GET", 200, 0.01)
    text = metrics.render().decode()
    for name in (
        "http_requests_total",
        "http_request_duration_seconds",
        "auth_codes_sent_total",
        "auth_code_failures_total",
        "auth_lockouts_total",
        "rate_limited_total",
        "email_send_failures_total",
    ):
        assert name in text


def test_allow_list_checks_socket_address() -> None:
    endpoint = MetricsEndpoint(Metrics(), ["127.0.0.1/32", "10.0.0.0/8"])
    assert endpoint.is_allowed("127.0.0.1")
    assert endpoint.is_allowed("10.1.2.3")
    assert not endpoint.is_allowed("203.0.113.9")
    assert not endpoint.is_allowed("not-an-ip")
    assert not endpoint.is_allowed(None)


def test_outside_client_gets_403() -> None:
    response = _client(Metrics(), ["127.0.0.1/32"]).get("/metrics/")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_allowed_client_gets_exposition() -> None:
    metrics = Metrics()
    metrics.rate_limited_total.labels(route="/auth/login").inc()

    class AllowAll(MetricsEndpoint):
        def is_allowed(self, client_host: str | None) -> bool:
            return client_host == "testclient"

    app = Starlette(routes=[Mount("/metrics", app=AllowAll(metrics, []))])
    response = TestClient(app).get("/metrics/")
    assert response.status_code == 200
    assert 'rate_limited_total{route="/auth/login"} 1.0' in response.text


def test_labels_never_carry_user_data() -> None:
    metrics = Metrics()
    metrics.observe_request("unmatched", "GET", 404, 0.001)
    text = metrics.render().decode()
    assert 'route="unmatched"' in text
    assert "@" not in text
