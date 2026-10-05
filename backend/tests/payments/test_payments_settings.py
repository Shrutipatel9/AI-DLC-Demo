"""Payment configuration (FR-016, FR7.3, NFR-008; U5 plan Step 1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.payments.fake_gateway import FakePaymentGateway, HttpWebhookDeliverer
from app.payments.public import build_payment_gateway
from app.payments.stripe_gateway import StripeGateway
from app.platform.settings import Settings
from tests.helpers import base_env, make_settings

STRIPE = {
    "PAYMENT_PROVIDER": "stripe",
    "STRIPE_SECRET_KEY": "sk_test_unused",
    "STRIPE_WEBHOOK_SECRET": "whsec_placeholder",
}


def test_price_and_currency_are_required_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    for missing in ("REPORT_PRICE_AMOUNT", "REPORT_PRICE_CURRENCY"):
        monkeypatch.delenv(missing, raising=False)  # scripts/ci-env.sh exports test values
        env = base_env()
        del env[missing]
        with pytest.raises(ValidationError, match=missing):
            Settings(_env_file=None, **env)  # type: ignore[arg-type]


@pytest.mark.parametrize("amount", ["0", "-5", "100000000", "12.5"])
def test_the_price_must_be_a_positive_whole_number_of_minor_units(amount: str) -> None:
    with pytest.raises(ValidationError, match="REPORT_PRICE_AMOUNT"):
        make_settings(REPORT_PRICE_AMOUNT=amount)


@pytest.mark.parametrize("currency", ["US", "USDT", "12$", ""])
def test_the_currency_must_be_a_three_letter_code(currency: str) -> None:
    with pytest.raises(ValidationError, match="REPORT_PRICE_CURRENCY"):
        make_settings(REPORT_PRICE_CURRENCY=currency)


def test_the_currency_is_stored_upper_case() -> None:
    assert make_settings(REPORT_PRICE_CURRENCY=" eur ").report_price_currency == "EUR"


@pytest.mark.parametrize("env", ["staging", "production"])
def test_the_fake_provider_is_refused_outside_development_and_test(env: str) -> None:
    with pytest.raises(ValidationError, match="PAYMENT_PROVIDER=fake"):
        make_settings(
            APP_ENV=env,
            PAYMENT_PROVIDER="fake",
            REFRESH_COOKIE_SECURE="true",
            EMAIL_BACKEND="smtp",
            SMTP_STARTTLS="true",
            RATE_LIMIT_BACKEND="postgres",
        )


@pytest.mark.parametrize("missing", ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"])
def test_stripe_needs_both_secrets(missing: str) -> None:
    values = dict(STRIPE)
    values[missing] = ""
    with pytest.raises(ValidationError, match=missing):
        make_settings(**values)


def test_return_urls_default_to_the_web_app_and_can_be_configured() -> None:
    assert make_settings().payment_return_urls == (
        "http://localhost:3000/payment/success",
        "http://localhost:3000/payment/cancel",
    )
    custom = make_settings(
        PAYMENT_SUCCESS_URL="https://app.example/paid", PAYMENT_CANCEL_URL="https://app.example/x"
    )
    assert custom.payment_return_urls == ("https://app.example/paid", "https://app.example/x")
    with pytest.raises(ValidationError, match="absolute http"):
        make_settings(PAYMENT_SUCCESS_URL="/payment/success")
    with pytest.raises(ValidationError, match="FAKE_PAYMENT_BASE_URL"):
        make_settings(FAKE_PAYMENT_BASE_URL="localhost:8000")


def test_the_provider_setting_picks_the_adapter() -> None:
    fake = build_payment_gateway(make_settings(FAKE_PAYMENT_BASE_URL="http://api.local:8000/"))
    assert isinstance(fake, FakePaymentGateway)
    deliverer = fake._deliver
    assert isinstance(deliverer, HttpWebhookDeliverer)
    assert deliverer.url == "http://api.local:8000/payments/stripe/webhook"
    stripe_gateway = build_payment_gateway(make_settings(**STRIPE))
    assert isinstance(stripe_gateway, StripeGateway)


def test_the_fake_signs_with_the_configured_secret_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)  # set by scripts/ci-env.sh
    fake = build_payment_gateway(make_settings(STRIPE_WEBHOOK_SECRET="whsec_configured"))
    assert isinstance(fake, FakePaymentGateway)
    assert fake._secret == "whsec_configured"
    random = build_payment_gateway(make_settings())
    assert isinstance(random, FakePaymentGateway)
    assert random._secret.startswith("whsec_fake_")
