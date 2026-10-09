"""Settings validators (BR7.1, BR7.2, NFR6.1, NFR6.2, NFR3.5; AC1.5.1-AC1.5.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.platform.settings import SettingsError, load_settings
from tests.helpers import base_env, make_settings, random_key


def test_valid_settings_decode_keys_and_defaults() -> None:
    settings = make_settings()
    keys = settings.jwt_keys()
    assert set(keys) == {"k1"}
    assert len(keys["k1"]) == 48
    assert len(settings.code_key()) == 48
    assert settings.access_token_ttl_seconds == 900
    assert settings.code_ttl_seconds == 600
    assert settings.code_resend_cooldown_seconds == 60
    assert settings.code_max_failures == 5
    assert settings.code_lock_seconds == 900
    assert settings.refresh_token_ttl_seconds == 604_800
    assert settings.auth_max_body_bytes == 16 * 1024


def test_short_jwt_key_is_refused_without_printing_it() -> None:
    short = random_key(16)
    with pytest.raises(ValidationError) as caught:
        make_settings(JWT_SIGNING_KEYS=json.dumps({"k1": short}))
    message = str(caught.value)
    assert "at least 32 bytes" in message
    assert short not in message


def test_unknown_active_kid_is_refused() -> None:
    with pytest.raises(ValidationError, match="JWT_ACTIVE_KID"):
        make_settings(JWT_ACTIVE_KID="missing")


@pytest.mark.parametrize("env", ["production", "staging"])
def test_fake_email_is_refused_outside_test_and_development(env: str) -> None:
    with pytest.raises(ValidationError, match="EMAIL_BACKEND=fake"):
        make_settings(APP_ENV=env, REFRESH_COOKIE_SECURE="true", RATE_LIMIT_BACKEND="postgres")


def test_insecure_cookie_is_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="REFRESH_COOKIE_SECURE=false"):
        make_settings(
            APP_ENV="production",
            EMAIL_BACKEND="smtp",
            SMTP_STARTTLS="true",
            RATE_LIMIT_BACKEND="postgres",
        )


def test_smtp_secret_required_only_when_real_adapter_uses_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # scripts/ci-env.sh blanks SMTP_PASSWORD for the whole test run; this test needs it unset.
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    # Fake adapter: no SMTP secret needed (AC1.5.3).
    assert make_settings(EMAIL_BACKEND="fake", SMTP_USERNAME="user").email_backend == "fake"
    # Real adapter with a username but no password: refused, naming the setting (AC1.5.2).
    with pytest.raises(ValidationError, match="SMTP_PASSWORD is required"):
        make_settings(EMAIL_BACKEND="smtp", SMTP_USERNAME="user", SMTP_PASSWORD=None)


def test_production_requires_tls_for_smtp() -> None:
    with pytest.raises(ValidationError, match="SMTP_STARTTLS"):
        make_settings(
            APP_ENV="production",
            EMAIL_BACKEND="smtp",
            REFRESH_COOKIE_SECURE="true",
            RATE_LIMIT_BACKEND="postgres",
        )


def test_load_settings_names_missing_values_but_never_prints_secrets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = base_env()
    secret = env["JWT_SIGNING_KEYS"]
    for key in list(env):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        if key != "CODE_HMAC_KEY":
            monkeypatch.setenv(key, value)
    monkeypatch.delenv("CODE_HMAC_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # no stray .env file
    with pytest.raises(SettingsError) as caught:
        load_settings()
    message = str(caught.value)
    assert "CODE_HMAC_KEY" in message
    assert secret not in message


def test_lists_accept_comma_separated_values_and_urls_use_psycopg() -> None:
    settings = make_settings(
        TRUSTED_PROXIES="10.0.0.1, 10.0.0.0/8",
        METRICS_ALLOW_CIDRS="127.0.0.1/32,::1/128",
        DATABASE_URL="postgresql://u:p@127.0.0.1:5432/db",
        FRONTEND_ORIGIN="http://localhost:3000/",
    )
    assert settings.trusted_proxies == ["10.0.0.1", "10.0.0.0/8"]
    assert settings.metrics_allow_cidrs == ["127.0.0.1/32", "::1/128"]
    assert settings.sqlalchemy_url.startswith("postgresql+psycopg://")
    assert settings.frontend_origin == "http://localhost:3000"
    with pytest.raises(ValidationError):
        make_settings(TRUSTED_PROXIES="not-an-ip")


def test_remote_smtp_login_without_tls_is_refused() -> None:
    # Gmail and other remote servers refuse login over plain text: fail at start-up instead.
    with pytest.raises(ValidationError, match="SMTP_STARTTLS must be true when logging in"):
        make_settings(
            EMAIL_BACKEND="smtp",
            SMTP_HOST="smtp.gmail.com",
            SMTP_PORT="587",
            SMTP_USERNAME="user",
            SMTP_PASSWORD="app-password",
            SMTP_STARTTLS="false",
        )
    tls = make_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="smtp.gmail.com",
        SMTP_USERNAME="user",
        SMTP_PASSWORD="app-password",
        SMTP_STARTTLS="true",
    )
    assert tls.smtp_starttls is True
    # Local Mailpit without TLS stays allowed.
    local = make_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="127.0.0.1",
        SMTP_USERNAME="user",
        SMTP_PASSWORD="x",
        SMTP_STARTTLS="false",
    )
    assert local.smtp_host == "127.0.0.1"
