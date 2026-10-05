"""U2 settings and their validators (NFR6.1, NFR2.5, NFR2.17; infrastructure post-review
R-03, R-05; D7)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.platform.settings import SettingsError, load_settings
from tests.helpers import base_env, make_settings, random_key


def test_u2_defaults() -> None:
    settings = make_settings()
    assert settings.refresh_token_days == 7
    assert settings.refresh_token_ttl_seconds == 604_800
    assert settings.reset_token_minutes == 10
    assert settings.refresh_attempt_recovery_seconds == 60
    assert settings.refresh_cookie_path == "/auth"
    assert settings.refresh_cookie_samesite == "lax"
    assert settings.csrf_origins == ["http://localhost:3000"]
    assert len(settings.email_key()) == 48


@pytest.mark.parametrize("value", [None, "change-me", random_key(16)])
def test_email_hash_key_is_required_and_at_least_32_bytes(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    env = base_env()
    env.pop("EMAIL_HASH_KEY")
    monkeypatch.delenv("EMAIL_HASH_KEY", raising=False)
    for key, item in env.items():
        monkeypatch.setenv(key, item)
    if value is not None:
        monkeypatch.setenv("EMAIL_HASH_KEY", value)
    monkeypatch.chdir("/")  # no .env file
    with pytest.raises(SettingsError) as caught:
        load_settings()
    message = str(caught.value)
    assert "EMAIL_HASH_KEY" in message
    if value:
        assert value not in message


@pytest.mark.parametrize("path", ["/", "/auth/refresh", "/api/auth"])
def test_the_refresh_cookie_path_must_be_auth(path: str) -> None:
    with pytest.raises(ValidationError, match="REFRESH_COOKIE_PATH must be /auth"):
        make_settings(REFRESH_COOKIE_PATH=path)


def test_samesite_none_needs_secure_and_unknown_values_are_refused() -> None:
    with pytest.raises(ValidationError, match="REFRESH_COOKIE_SAMESITE=none requires"):
        make_settings(REFRESH_COOKIE_SAMESITE="none", REFRESH_COOKIE_SECURE="false")
    assert (
        make_settings(
            REFRESH_COOKIE_SAMESITE="none", REFRESH_COOKIE_SECURE="true"
        ).refresh_cookie_samesite
        == "none"
    )
    with pytest.raises(ValidationError):
        make_settings(REFRESH_COOKIE_SAMESITE="sometimes")


def test_csrf_origins_are_normalised_and_bad_values_refused() -> None:
    settings = make_settings(
        CSRF_ALLOWED_ORIGINS="HTTPS://App.Example.com:443/, http://localhost:3000, "
        "https://app.example.com"
    )
    assert settings.csrf_origins == ["https://app.example.com", "http://localhost:3000"]
    with pytest.raises(ValidationError, match="CSRF_ALLOWED_ORIGINS"):
        make_settings(CSRF_ALLOWED_ORIGINS="app.example.com")
    assert make_settings(FRONTEND_ORIGIN="http://LOCALHOST:3000/").frontend_origin == (
        "http://localhost:3000"
    )


def test_lifetimes_and_limits_are_bounded() -> None:
    assert make_settings(REFRESH_RATE_LIMIT_PER_MINUTE="120").refresh_rate_limit_per_window == 120
    for name, value in (
        ("REFRESH_TOKEN_DAYS", "0"),
        ("RESET_TOKEN_MINUTES", "0"),
        ("REFRESH_ATTEMPT_RECOVERY_SECONDS", "0"),
        ("REFRESH_RATE_LIMIT_PER_MINUTE", "0"),
    ):
        with pytest.raises(ValidationError):
            make_settings(**{name: value})
