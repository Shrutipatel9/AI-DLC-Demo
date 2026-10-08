"""Typed application settings (BR7.1, BR7.2, NFR6.1, NFR6.2, NFR3.5).

Every tunable value and every secret is read from the environment or a local
``.env`` file. Nothing environment-specific is hard-coded. Validation runs at
start-up, so a missing or unsafe value stops the process with a message that
names the setting but never prints a secret value.
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AppEnv = Literal["development", "test", "staging", "production"]
EmailBackend = Literal["smtp", "fake"]
RateLimitBackend = Literal["postgres", "memory"]
SameSite = Literal["lax", "strict", "none"]
MediaBackend = Literal["local"]
PaymentProvider = Literal["stripe", "fake"]
AiProvider = Literal["openai", "fake"]
FakeAiProfile = Literal["instant", "realistic"]

#: Angle ids (``front``, ``left_3q`` ...): also used as URL path segments and storage names.
_ANGLE_ID = re.compile(r"[a-z][a-z0-9_]{0,31}")

MIN_KEY_BYTES = 32
INSECURE_ENVIRONMENTS: frozenset[str] = frozenset({"development", "test"})
#: The refresh cookie must cover /auth/refresh, /auth/logout and /auth/change-password
#: (U2 functional design post-review R-03, NFR2.5).
REQUIRED_REFRESH_COOKIE_PATH = "/auth"
_DEFAULT_PORTS = {"http": 80, "https": 443}
SECONDS_PER_DAY = 86_400


def normalise_origin(value: str) -> str:
    """Normalise an origin to ``scheme://host[:port]`` (U2 NFR design post-review R-06).

    Lower-cases the scheme and host, drops a trailing slash, any path, and the default
    port for the scheme, so CORS and the CSRF check compare like with like.

    Raises:
        ValueError: If the value is not an http(s) origin with a host.
    """
    parts = urlsplit(value.strip())
    scheme = parts.scheme.lower()
    if scheme not in _DEFAULT_PORTS or not parts.hostname:
        raise ValueError("an origin must look like http(s)://host[:port]")
    host = parts.hostname.lower()
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("an origin has an invalid port") from exc
    if port is None or port == _DEFAULT_PORTS[scheme]:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


_CURRENCY = re.compile(r"[A-Za-z]{3}")


def _is_http_url(value: str) -> bool:
    """True for an absolute ``http(s)://host...`` URL."""
    parts = urlsplit(value)
    return parts.scheme in _DEFAULT_PORTS and bool(parts.hostname)


def _split_csv(value: object) -> object:
    """Accept a comma-separated string as a list (``"a, b"`` -> ``["a", "b"]``)."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            return json.loads(stripped)
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return value


def parse_yaw_ranges(raw: str) -> dict[str, tuple[float, float]]:
    """Parse ``PHOTO_POSE_YAW_RANGES`` (``{"angle": [min_degrees, max_degrees]}``).

    Raises:
        ValueError: If the JSON is malformed, an angle id is invalid or a range is reversed.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("PHOTO_POSE_YAW_RANGES must be a JSON object") from exc
    if not isinstance(data, dict):
        raise ValueError("PHOTO_POSE_YAW_RANGES must be a JSON object")
    ranges: dict[str, tuple[float, float]] = {}
    for angle, bounds in data.items():
        if not isinstance(angle, str) or not _ANGLE_ID.fullmatch(angle):
            raise ValueError("PHOTO_POSE_YAW_RANGES keys must be angle ids")
        if (
            not isinstance(bounds, list)
            or len(bounds) != 2
            or not all(isinstance(b, int | float) and not isinstance(b, bool) for b in bounds)
            or not -90 <= bounds[0] < bounds[1] <= 90
        ):
            raise ValueError("PHOTO_POSE_YAW_RANGES values must be [min, max] within -90..90")
        ranges[angle] = (float(bounds[0]), float(bounds[1]))
    return ranges


#: [Decided by delivery team] Symmetry label bands: ``label -> minimum score`` (a score on a
#: band's lower boundary gets that band's label; AC7.5.2). Placeholder values to calibrate.
DEFAULT_SYMMETRY_BANDS = '{"Excellent": 90, "Good": 75, "Moderate": 55, "Fair": 35, "Low": 0}'


def parse_symmetry_bands(raw: str) -> tuple[tuple[str, float], ...]:
    """Parse ``SYMMETRY_LABEL_BANDS`` into ``(label, minimum score)``, highest band first.

    Raises:
        ValueError: If the JSON is malformed, a label is empty, a minimum is outside 0..100
            or repeated, or no band starts at 0 (every score must get a label).
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("SYMMETRY_LABEL_BANDS must be a JSON object") from exc
    if not isinstance(data, dict) or not data:
        raise ValueError("SYMMETRY_LABEL_BANDS must be a non-empty JSON object")
    bands: list[tuple[str, float]] = []
    for label, minimum in data.items():
        if (
            not isinstance(label, str)
            or not label.strip()
            or not isinstance(minimum, int | float)
            or isinstance(minimum, bool)
            or not 0 <= minimum <= 100
        ):
            raise ValueError("SYMMETRY_LABEL_BANDS maps a label to a minimum score of 0-100")
        bands.append((label.strip(), float(minimum)))
    minimums = [minimum for _, minimum in bands]
    if len(set(minimums)) != len(minimums) or 0.0 not in minimums:
        raise ValueError("SYMMETRY_LABEL_BANDS minimums must be distinct and include 0")
    return tuple(sorted(bands, key=lambda band: band[1], reverse=True))


def decode_key(raw: str, setting_name: str) -> bytes:
    """Decode a base64 key and enforce the minimum length.

    Args:
        raw: The base64 text from configuration.
        setting_name: Name used in the error message (the value is never shown).

    Returns:
        The decoded key bytes.

    Raises:
        ValueError: If the text is not base64 or decodes to fewer than 32 bytes.
    """
    try:
        key = base64.b64decode(raw.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{setting_name} must be base64-encoded") from exc
    if len(key) < MIN_KEY_BYTES:
        raise ValueError(f"{setting_name} must decode to at least {MIN_KEY_BYTES} bytes")
    return key


class Settings(BaseSettings):
    """All configuration for the API process.

    Defaults are safe for local development only where noted. Secrets have no
    default and are required.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    # --- Environment -----------------------------------------------------------
    app_env: AppEnv = Field(default="development", alias="APP_ENV")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )

    # --- Database ----------------------------------------------------------------
    database_url: SecretStr = Field(alias="DATABASE_URL")
    db_pool_size: int = Field(default=5, ge=1, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=5, ge=0, alias="DB_MAX_OVERFLOW")
    db_pool_timeout_seconds: float = Field(default=5.0, gt=0, alias="DB_POOL_TIMEOUT")
    db_pool_recycle_seconds: int = Field(default=1800, gt=0, alias="DB_POOL_RECYCLE")
    check_migrations_at_startup: bool = Field(default=True, alias="CHECK_MIGRATIONS_AT_STARTUP")

    # --- HTTP / CORS ---------------------------------------------------------------
    frontend_origin: str = Field(alias="FRONTEND_ORIGIN")
    auth_max_body_bytes: int = Field(default=16 * 1024, gt=0, alias="AUTH_MAX_BODY_BYTES")
    trusted_proxies: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="TRUSTED_PROXIES"
    )

    # --- Access tokens (NFR2.6) ------------------------------------------------------
    jwt_signing_keys: SecretStr = Field(alias="JWT_SIGNING_KEYS")
    jwt_active_kid: str = Field(alias="JWT_ACTIVE_KID")
    access_token_ttl_seconds: int = Field(default=900, gt=0, alias="ACCESS_TOKEN_TTL_SECONDS")

    # --- One-time codes (NFR2.5) -------------------------------------------------------
    code_hmac_key: SecretStr = Field(alias="CODE_HMAC_KEY")
    code_ttl_seconds: int = Field(default=600, gt=0, alias="CODE_TTL_SECONDS")
    code_resend_cooldown_seconds: int = Field(
        default=60, gt=0, alias="CODE_RESEND_COOLDOWN_SECONDS"
    )
    code_max_failures: int = Field(default=5, ge=1, alias="CODE_MAX_FAILURES")
    code_lock_seconds: int = Field(default=900, gt=0, alias="CODE_LOCK_SECONDS")

    # --- CSRF allow-list (U2 NFR2.7, NFR2.17) ------------------------------------------------
    #: Origins allowed by the CSRF check on the cookie endpoints and by CORS. Empty means
    #: "the value of FRONTEND_ORIGIN". Values are normalised (see ``normalise_origin``).
    csrf_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="CSRF_ALLOWED_ORIGINS"
    )

    # --- Refresh sessions and cookie (NFR2.7; U2 NFR2.1-NFR2.5, NFR6.1) ----------------------
    refresh_token_days: int = Field(default=7, ge=1, le=90, alias="REFRESH_TOKEN_DAYS")
    refresh_attempt_recovery_seconds: int = Field(
        default=60, ge=1, le=600, alias="REFRESH_ATTEMPT_RECOVERY_SECONDS"
    )
    refresh_cookie_name: str = Field(default="refresh_token", alias="REFRESH_COOKIE_NAME")
    refresh_cookie_path: str = Field(default="/auth", alias="REFRESH_COOKIE_PATH")
    refresh_cookie_samesite: SameSite = Field(default="lax", alias="REFRESH_COOKIE_SAMESITE")
    refresh_cookie_secure: bool = Field(default=True, alias="REFRESH_COOKIE_SECURE")
    refresh_cookie_domain: str | None = Field(default=None, alias="REFRESH_COOKIE_DOMAIN")

    # --- Password reset and anti-enumeration (U2 NFR2.9, NFR2.11, NFR6.1) -------------------
    reset_token_minutes: int = Field(default=10, ge=1, le=60, alias="RESET_TOKEN_MINUTES")
    #: Keyed hash for shadow counters of unknown emails (HMAC-SHA-256, base64, >= 32 bytes).
    email_hash_key: SecretStr = Field(alias="EMAIL_HASH_KEY")

    # --- Password hashing (NFR2.2, OWASP Argon2id minimum) -------------------------------
    argon2_memory_kib: int = Field(default=19_456, ge=8, alias="ARGON2_MEMORY_KIB")
    argon2_time_cost: int = Field(default=2, ge=1, alias="ARGON2_TIME_COST")
    argon2_parallelism: int = Field(default=1, ge=1, alias="ARGON2_PARALLELISM")

    # --- Email (NFR12.1, NFR5.1-NFR5.3) --------------------------------------------------
    email_backend: EmailBackend = Field(default="smtp", alias="EMAIL_BACKEND")
    email_from: str = Field(default="no-reply@localhost", alias="EMAIL_FROM")
    smtp_host: str = Field(default="127.0.0.1", alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, gt=0, lt=65536, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: SecretStr | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_starttls: bool = Field(default=False, alias="SMTP_STARTTLS")
    email_attempt_timeout_seconds: float = Field(default=10.0, gt=0, alias="EMAIL_TIMEOUT_SECONDS")
    email_send_budget_seconds: float = Field(default=25.0, gt=0, alias="EMAIL_SEND_BUDGET_SECONDS")
    email_max_attempts: int = Field(default=3, ge=1, alias="EMAIL_MAX_ATTEMPTS")
    email_max_concurrency: int = Field(default=10, ge=1, alias="EMAIL_MAX_CONCURRENCY")
    auth_email_hourly_cap: int = Field(default=500, ge=1, alias="AUTH_EMAIL_HOURLY_CAP")

    # --- Per-IP throttling (NFR2.9) --------------------------------------------------------
    rate_limit_backend: RateLimitBackend = Field(default="postgres", alias="RATE_LIMIT_BACKEND")
    auth_rate_limit_per_window: int = Field(default=20, ge=1, alias="AUTH_RATE_LIMIT_PER_MINUTE")
    auth_rate_limit_window_seconds: int = Field(
        default=60, ge=1, alias="AUTH_RATE_LIMIT_WINDOW_SECONDS"
    )
    #: Separate, higher per-IP limit for /auth/refresh and /auth/logout (U2 NFR2.13):
    #: many tabs behind one NAT refresh legitimately.
    refresh_rate_limit_per_window: int = Field(
        default=60, ge=1, alias="REFRESH_RATE_LIMIT_PER_MINUTE"
    )

    # --- Onboarding (U3; plan decisions D1, D2) -----------------------------------------------
    #: Consent text file (JSON: version, text, agreement). Empty = the bundled consent_v1.json.
    onboarding_consent_file: Path | None = Field(default=None, alias="ONBOARDING_CONSENT_FILE")
    #: Questionnaire definition file. Empty = the bundled questionnaire_v1.json ([QS]).
    onboarding_questionnaire_file: Path | None = Field(
        default=None, alias="ONBOARDING_QUESTIONNAIRE_FILE"
    )
    #: Optional professional-support link shown when the disclaimer cannot be confirmed
    #: (AC4.3.4). None is invented: empty means no link is shown.
    onboarding_support_url: str | None = Field(default=None, alias="ONBOARDING_SUPPORT_URL")

    # --- Media storage (U4; US1.10, ADR-009) ----------------------------------------------------
    #: Only ``local`` (a private directory on disk) exists today; an object store adapter can
    #: be added behind the same FileStorage port once a host is chosen (NFR-010).
    media_backend: MediaBackend = Field(default="local", alias="MEDIA_BACKEND")
    #: Private directory for stored files. Never served as static files (AC1.10.2).
    media_root: Path = Field(default=Path("var/media"), alias="MEDIA_ROOT")

    # --- Face landmarks (U4; US1.11, ASM-010) --------------------------------------------------
    #: The pinned MediaPipe Face Landmarker model (fetched by ``tools.fetch_face_model``).
    face_model_path: Path = Field(
        default=Path("var/models/face_landmarker.task"), alias="FACE_MODEL_PATH"
    )
    #: Load (and SHA-256 check) the model at start-up so a missing model fails fast.
    face_model_preload: bool = Field(default=True, alias="FACE_MODEL_PRELOAD")
    #: Development/test only: JSON of image pixel hash -> landmarks used instead of the model
    #: for those images (the E2E "different person" fixtures). Empty = not used.
    face_landmark_overrides_file: Path | None = Field(
        default=None, alias="FACE_LANDMARK_OVERRIDES_FILE"
    )

    # --- Photos (U4; FR-005, FR-006, BR-005, ASM-002, ASM-005, ASM-010) ------------------------
    #: The required angles, in order (ASM-005: a single configurable value).
    photo_angles: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["front", "left_3q", "right_3q"], alias="PHOTO_ANGLES"
    )
    #: Photo catalog (rules, guidance, angles with pose ranges). Empty = bundled catalog_v1.json.
    photo_catalog_file: Path | None = Field(default=None, alias="PHOTO_CATALOG_FILE")
    #: Optional per-angle yaw ranges in degrees, JSON ``{"angle": [min, max]}``; overrides the
    #: catalog's ranges for the angles it names. Empty = the catalog values.
    photo_pose_yaw_ranges: str | None = Field(default=None, alias="PHOTO_POSE_YAW_RANGES")
    photo_max_upload_bytes: int = Field(
        default=10 * 1024 * 1024, gt=0, alias="PHOTO_MAX_UPLOAD_BYTES"
    )
    #: Stored photos are downscaled so their longer side is at most this many pixels.
    photo_max_dimension: int = Field(default=2048, ge=256, alias="PHOTO_MAX_DIMENSION")
    photo_min_width: int = Field(default=480, ge=1, alias="PHOTO_MIN_WIDTH")
    photo_min_height: int = Field(default=480, ge=1, alias="PHOTO_MIN_HEIGHT")
    #: Mean luminance (0-255) of the face region.
    photo_min_brightness: float = Field(default=60.0, ge=0, le=255, alias="PHOTO_MIN_BRIGHTNESS")
    photo_max_brightness: float = Field(default=230.0, ge=0, le=255, alias="PHOTO_MAX_BRIGHTNESS")
    #: Face landmark box area as a fraction of the image area.
    photo_min_face_fraction: float = Field(
        default=0.05, gt=0, lt=1, alias="PHOTO_MIN_FACE_FRACTION"
    )
    photo_max_face_fraction: float = Field(default=0.8, gt=0, le=1, alias="PHOTO_MAX_FACE_FRACTION")
    #: Eyes/mouth count as covered when their mean luminance is below this ratio of the
    #: cheeks' (dark glasses, a hat's shadow) ...
    photo_occlusion_dark_ratio: float = Field(
        default=0.35, gt=0, lt=1, alias="PHOTO_OCCLUSION_DARK_RATIO"
    )
    #: ... or their luminance spread (std / cheek mean) is below this (a hand, a mask).
    photo_occlusion_min_contrast: float = Field(
        default=0.06, gt=0, lt=1, alias="PHOTO_OCCLUSION_MIN_CONTRAST"
    )
    #: Same-person threshold: a pair whose signature distance is <= this matches (ASM-010).
    identity_threshold: float = Field(default=0.6, gt=0, alias="IDENTITY_THRESHOLD")

    # --- Payments (U5; FR-015, FR-016, FR7.2-FR7.5, OQ-002) -------------------------------------
    #: The report price in minor units (cents). Required: the price is still open (OQ-002), so
    #: nothing is hard-coded (FR-016).
    report_price_amount: int = Field(gt=0, le=99_999_999, alias="REPORT_PRICE_AMOUNT")
    #: ISO 4217 currency code, for example ``USD`` (stored upper-case).
    report_price_currency: str = Field(alias="REPORT_PRICE_CURRENCY")
    #: ``stripe`` (hosted Checkout through the Stripe SDK) or ``fake`` (development/test only).
    payment_provider: PaymentProvider = Field(default="stripe", alias="PAYMENT_PROVIDER")
    stripe_secret_key: SecretStr | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    #: The webhook signing secret (``whsec_...``). The fake signs with it too when set.
    stripe_webhook_secret: SecretStr | None = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    #: Contract section 6: Stripe API calls time out after 10 s and are retried once.
    stripe_timeout_seconds: float = Field(default=10.0, gt=0, alias="STRIPE_TIMEOUT_SECONDS")
    stripe_max_network_retries: int = Field(
        default=1, ge=0, le=5, alias="STRIPE_MAX_NETWORK_RETRIES"
    )
    #: Where Stripe sends the user back. Empty = ``FRONTEND_ORIGIN`` + /payment/success|cancel.
    payment_success_url: str | None = Field(default=None, alias="PAYMENT_SUCCESS_URL")
    payment_cancel_url: str | None = Field(default=None, alias="PAYMENT_CANCEL_URL")
    #: How long the "confirming your payment" screen waits before it says the payment is
    #: still being confirmed (AC6.5.3).
    payment_confirm_wait_seconds: int = Field(
        default=30, ge=1, le=600, alias="PAYMENT_CONFIRM_WAIT_SECONDS"
    )
    #: Fake provider only: the API's own public URL (its hosted test page and the webhook
    #: it posts to) and how long it waits before posting the signed webhook.
    fake_payment_base_url: str = Field(
        default="http://localhost:8000", alias="FAKE_PAYMENT_BASE_URL"
    )
    fake_payment_webhook_delay_seconds: float = Field(
        default=2.0, ge=0, le=60, alias="FAKE_PAYMENT_WEBHOOK_DELAY_SECONDS"
    )

    # --- AI vendors (U6; US1.12, FR-008, NFR-008, NFR-013, ASM-011) ---------------------------
    #: ``openai`` or ``fake`` (development/test only). The image vendor is chosen separately so
    #: it can be swapped without touching code (AC1.12.1).
    ai_text_provider: AiProvider = Field(default="fake", alias="AI_TEXT_PROVIDER")
    ai_image_provider: AiProvider = Field(default="fake", alias="AI_IMAGE_PROVIDER")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    #: Model names are configuration, never code (NFR-008); required with the ``openai`` adapter.
    openai_text_model: str | None = Field(default=None, alias="OPENAI_TEXT_MODEL")
    openai_image_model: str | None = Field(default=None, alias="OPENAI_IMAGE_MODEL")
    #: Contract section 6: every adapter call has a timeout.
    ai_text_timeout_seconds: float = Field(default=90.0, gt=0, alias="AI_TEXT_TIMEOUT_SECONDS")
    ai_image_timeout_seconds: float = Field(default=120.0, gt=0, alias="AI_IMAGE_TIMEOUT_SECONDS")
    #: Attempts at the report-writing step (invalid output or a vendor error each use one).
    ai_text_max_attempts: int = Field(default=3, ge=1, le=10, alias="AI_TEXT_MAX_ATTEMPTS")
    #: Automatic retries after an image's first attempt: 1 + 3 = 4 calls at most (AC9.5.1,
    #: AC9.5.2); rate-limit answers count as attempts too (AC7.6.4).
    ai_image_auto_retries: int = Field(default=3, ge=0, le=10, alias="AI_IMAGE_AUTO_RETRIES")
    #: [Decided by delivery team] (Q10, AC9.5.4) Manual retries a user may use per image slot.
    ai_image_manual_retry_limit: int = Field(
        default=3, ge=0, le=10, alias="AI_IMAGE_MANUAL_RETRY_LIMIT"
    )
    #: The image-edit fidelity setting sent with every request (AC9.1.2, ASM-011): the output
    #: keeps the person's face. A vendor-specific value, so it is configuration (NFR-013).
    ai_image_fidelity: str = Field(default="high", min_length=1, alias="AI_IMAGE_FIDELITY")
    ai_retry_backoff_seconds: float = Field(default=2.0, ge=0, alias="AI_RETRY_BACKOFF_SECONDS")
    #: How many images are generated at once (AC7.6.4); used by U7.
    ai_image_concurrency: int = Field(default=4, ge=1, le=16, alias="AI_IMAGE_CONCURRENCY")
    #: Fakes only: ``instant`` or the committed ``realistic`` latency profile (AC7.2.5).
    ai_fake_profile: FakeAiProfile = Field(default="instant", alias="AI_FAKE_PROFILE")
    #: Fakes only: an extra pause per text call (lets browser journeys see a step in progress).
    ai_fake_text_delay_seconds: float = Field(
        default=0.0, ge=0, le=60, alias="AI_FAKE_TEXT_DELAY_SECONDS"
    )
    #: Fakes only: a directory whose ``fail-text`` file (a count) makes the next text calls fail.
    ai_fake_control_dir: Path | None = Field(default=None, alias="AI_FAKE_CONTROL_DIR")

    # --- Analysis (U6; FR-007, FR-008, FR8.2, NFR4, US7.x) -----------------------------------
    #: Shown on the progress screen; within NFR4's 10 minutes (AC7.2.2).
    analysis_expected_wait_minutes: int = Field(
        default=8, ge=1, le=10, alias="ANALYSIS_EXPECTED_WAIT_MINUTES"
    )
    #: [Decided by delivery team] The reassuring-tone instruction is added when Q20 (distress)
    #: or Q21 (how often they think about their appearance) is at or above these answers
    #: (AC7.4.3). Values are answer option values of the questionnaire.
    tone_distress_trigger: str = Field(default="moderate", alias="TONE_DISTRESS_TRIGGER")
    tone_frequency_trigger: str = Field(default="frequently", alias="TONE_FREQUENCY_TRIGGER")
    #: JSON ``{"label": minimum score}`` (AC7.5.2); see ``parse_symmetry_bands``.
    symmetry_label_bands: str = Field(default=DEFAULT_SYMMETRY_BANDS, alias="SYMMETRY_LABEL_BANDS")
    #: Stored measurements are rounded to this many decimals; narratives must cite them at
    #: exactly this precision (AC7.9.1).
    report_value_decimals: int = Field(default=2, ge=0, le=4, alias="REPORT_VALUE_DECIMALS")

    # --- Background worker (U6; US1.7) ------------------------------------------------------
    worker_poll_interval_seconds: float = Field(
        default=1.0, gt=0, alias="WORKER_POLL_INTERVAL_SECONDS"
    )
    worker_heartbeat_seconds: float = Field(default=10.0, gt=0, alias="WORKER_HEARTBEAT_SECONDS")
    #: A running job whose heartbeat is older than this belongs to a dead worker (AC1.7.2).
    worker_stale_after_seconds: float = Field(
        default=60.0, gt=0, alias="WORKER_STALE_AFTER_SECONDS"
    )
    #: A job is started (or resumed after a worker died) at most this many times.
    job_max_attempts: int = Field(default=3, ge=1, le=10, alias="JOB_MAX_ATTEMPTS")

    # --- Metrics (NFR5.10) ------------------------------------------------------------------
    metrics_enabled: bool = Field(default=False, alias="METRICS_ENABLED")
    metrics_allow_cidrs: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["127.0.0.1/32"], alias="METRICS_ALLOW_CIDRS"
    )

    # ----------------------------------------------------------------------------------------
    @field_validator(
        "trusted_proxies", "metrics_allow_cidrs", "csrf_allowed_origins", mode="before"
    )
    @classmethod
    def _parse_csv(cls, value: object) -> object:
        return _split_csv(value)

    @field_validator("csrf_allowed_origins")
    @classmethod
    def _validate_csrf_origins(cls, value: list[str]) -> list[str]:
        normalised: list[str] = []
        for entry in value:
            try:
                origin = normalise_origin(entry)
            except ValueError as exc:
                raise ValueError(f"CSRF_ALLOWED_ORIGINS: {exc}") from None
            if origin not in normalised:
                normalised.append(origin)
        return normalised

    @field_validator("refresh_cookie_path")
    @classmethod
    def _validate_cookie_path(cls, value: str) -> str:
        if value != REQUIRED_REFRESH_COOKIE_PATH:
            raise ValueError("REFRESH_COOKIE_PATH must be /auth")
        return value

    @field_validator("email_hash_key")
    @classmethod
    def _validate_email_hash_key(cls, value: SecretStr) -> SecretStr:
        decode_key(value.get_secret_value(), "EMAIL_HASH_KEY")
        return value

    @field_validator("trusted_proxies", "metrics_allow_cidrs")
    @classmethod
    def _validate_networks(cls, value: list[str]) -> list[str]:
        for entry in value:
            ipaddress.ip_network(entry, strict=False)
        return value

    @field_validator("frontend_origin")
    @classmethod
    def _validate_origin(cls, value: str) -> str:
        origin = value.strip().rstrip("/")
        if not origin.startswith(("http://", "https://")):
            raise ValueError("FRONTEND_ORIGIN must start with http:// or https://")
        try:
            return normalise_origin(origin)
        except ValueError as exc:
            raise ValueError(f"FRONTEND_ORIGIN: {exc}") from None

    @field_validator(
        "onboarding_consent_file",
        "onboarding_questionnaire_file",
        "face_landmark_overrides_file",
        "photo_catalog_file",
        "photo_pose_yaw_ranges",
        "ai_fake_control_dir",
        "openai_api_key",
        "openai_text_model",
        "openai_image_model",
        mode="before",
    )
    @classmethod
    def _empty_path_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("photo_angles", mode="before")
    @classmethod
    def _parse_angles(cls, value: object) -> object:
        return _split_csv(value)

    @field_validator("photo_angles")
    @classmethod
    def _validate_angles(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("PHOTO_ANGLES must name at least one angle")
        if len(set(value)) != len(value):
            raise ValueError("PHOTO_ANGLES must not repeat an angle")
        for angle in value:
            if not _ANGLE_ID.fullmatch(angle):
                raise ValueError("PHOTO_ANGLES entries must look like front or left_3q")
        return value

    @field_validator("photo_pose_yaw_ranges")
    @classmethod
    def _validate_yaw_ranges(cls, value: str | None) -> str | None:
        if value is not None:
            parse_yaw_ranges(value)
        return value

    @field_validator("report_price_currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        code = value.strip()
        if not _CURRENCY.fullmatch(code):
            raise ValueError("REPORT_PRICE_CURRENCY must be a 3-letter ISO 4217 code such as USD")
        return code.upper()

    @field_validator("payment_success_url", "payment_cancel_url", mode="before")
    @classmethod
    def _validate_return_url(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if not isinstance(value, str) or not _is_http_url(value.strip()):
            raise ValueError("payment return URLs must be absolute http(s) URLs")
        return value.strip()

    @field_validator("fake_payment_base_url")
    @classmethod
    def _validate_fake_base_url(cls, value: str) -> str:
        url = value.strip().rstrip("/")
        if not _is_http_url(url):
            raise ValueError("FAKE_PAYMENT_BASE_URL must be an absolute http(s) URL")
        return url

    @field_validator("onboarding_support_url", mode="before")
    @classmethod
    def _validate_support_url(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if not isinstance(value, str) or not value.strip().lower().startswith("https://"):
            raise ValueError("ONBOARDING_SUPPORT_URL must be an https:// URL")
        return value.strip()

    @field_validator("openai_base_url")
    @classmethod
    def _validate_openai_base_url(cls, value: str) -> str:
        url = value.strip().rstrip("/")
        if not _is_http_url(url):
            raise ValueError("OPENAI_BASE_URL must be an absolute http(s) URL")
        return url

    @field_validator("symmetry_label_bands")
    @classmethod
    def _validate_symmetry_bands(cls, value: str) -> str:
        parse_symmetry_bands(value)
        return value

    @field_validator("code_hmac_key")
    @classmethod
    def _validate_code_key(cls, value: SecretStr) -> SecretStr:
        decode_key(value.get_secret_value(), "CODE_HMAC_KEY")
        return value

    @model_validator(mode="after")
    def _validate_cross_field_rules(self) -> Settings:
        keys = self.jwt_keys()
        if self.jwt_active_kid not in keys:
            raise ValueError("JWT_ACTIVE_KID must name a key in JWT_SIGNING_KEYS")
        if self.email_backend == "fake" and self.app_env not in INSECURE_ENVIRONMENTS:
            raise ValueError(
                "EMAIL_BACKEND=fake is only allowed when APP_ENV is development or test"
            )
        if not self.refresh_cookie_secure and self.app_env not in INSECURE_ENVIRONMENTS:
            raise ValueError(
                "REFRESH_COOKIE_SECURE=false is only allowed when APP_ENV is development or test"
            )
        if self.refresh_cookie_samesite == "none" and not self.refresh_cookie_secure:
            raise ValueError("REFRESH_COOKIE_SAMESITE=none requires REFRESH_COOKIE_SECURE=true")
        if self.email_backend == "smtp" and self.smtp_username and self.smtp_password is None:
            raise ValueError("SMTP_PASSWORD is required when SMTP_USERNAME is set")
        if (
            self.email_backend == "smtp"
            and self.app_env not in INSECURE_ENVIRONMENTS
            and not self.smtp_starttls
        ):
            raise ValueError("SMTP_STARTTLS must be true outside development and test")
        if self.rate_limit_backend == "memory" and self.app_env not in INSECURE_ENVIRONMENTS:
            raise ValueError(
                "RATE_LIMIT_BACKEND=memory is only allowed when APP_ENV is development or test"
            )
        if (
            self.face_landmark_overrides_file is not None
            and self.app_env not in INSECURE_ENVIRONMENTS
        ):
            raise ValueError(
                "FACE_LANDMARK_OVERRIDES_FILE is only allowed when APP_ENV is development or test"
            )
        if self.photo_min_brightness >= self.photo_max_brightness:
            raise ValueError("PHOTO_MIN_BRIGHTNESS must be below PHOTO_MAX_BRIGHTNESS")
        if self.photo_min_face_fraction >= self.photo_max_face_fraction:
            raise ValueError("PHOTO_MIN_FACE_FRACTION must be below PHOTO_MAX_FACE_FRACTION")
        self._validate_payment_rules()
        self._validate_ai_rules()
        if self.worker_stale_after_seconds <= self.worker_heartbeat_seconds:
            raise ValueError("WORKER_STALE_AFTER_SECONDS must exceed WORKER_HEARTBEAT_SECONDS")
        return self

    def _validate_ai_rules(self) -> None:
        providers = {
            "AI_TEXT_PROVIDER": (
                self.ai_text_provider,
                self.openai_text_model,
                "OPENAI_TEXT_MODEL",
            ),
            "AI_IMAGE_PROVIDER": (
                self.ai_image_provider,
                self.openai_image_model,
                "OPENAI_IMAGE_MODEL",
            ),
        }
        for name, (provider, model, model_name) in providers.items():
            if provider == "fake" and self.app_env not in INSECURE_ENVIRONMENTS:
                raise ValueError(f"{name}=fake is only allowed when APP_ENV is development or test")
            if provider == "openai":
                if self.openai_api_key is None or not self.openai_api_key.get_secret_value():
                    raise ValueError(f"OPENAI_API_KEY is required when {name}=openai")
                if not model:
                    raise ValueError(f"{model_name} is required when {name}=openai")

    def _validate_payment_rules(self) -> None:
        if self.payment_provider == "fake" and self.app_env not in INSECURE_ENVIRONMENTS:
            raise ValueError(
                "PAYMENT_PROVIDER=fake is only allowed when APP_ENV is development or test"
            )
        if self.payment_provider == "stripe":
            if self.stripe_secret_key is None or not self.stripe_secret_key.get_secret_value():
                raise ValueError("STRIPE_SECRET_KEY is required when PAYMENT_PROVIDER=stripe")
            if (
                self.stripe_webhook_secret is None
                or not self.stripe_webhook_secret.get_secret_value()
            ):
                raise ValueError("STRIPE_WEBHOOK_SECRET is required when PAYMENT_PROVIDER=stripe")

    @property
    def payment_return_urls(self) -> tuple[str, str]:
        """``(success_url, cancel_url)``; defaults are the web app's payment screens."""
        return (
            self.payment_success_url or f"{self.frontend_origin}/payment/success",
            self.payment_cancel_url or f"{self.frontend_origin}/payment/cancel",
        )

    @property
    def symmetry_bands(self) -> tuple[tuple[str, float], ...]:
        """``SYMMETRY_LABEL_BANDS`` parsed, highest band first."""
        return parse_symmetry_bands(self.symmetry_label_bands)

    def yaw_range_overrides(self) -> dict[str, tuple[float, float]]:
        """``PHOTO_POSE_YAW_RANGES`` parsed (empty when not set)."""
        if self.photo_pose_yaw_ranges is None:
            return {}
        return parse_yaw_ranges(self.photo_pose_yaw_ranges)

    # ----------------------------------------------------------------------------------------
    def jwt_keys(self) -> dict[str, bytes]:
        """Return the decoded signing keys, keyed by ``kid``.

        Raises:
            ValueError: If the JSON is malformed or any key is shorter than 32 bytes.
        """
        try:
            raw = json.loads(self.jwt_signing_keys.get_secret_value())
        except json.JSONDecodeError as exc:
            raise ValueError("JWT_SIGNING_KEYS must be a JSON object of kid -> base64 key") from exc
        if not isinstance(raw, dict) or not raw:
            raise ValueError("JWT_SIGNING_KEYS must be a non-empty JSON object")
        keys: dict[str, bytes] = {}
        for kid, encoded in raw.items():
            if not isinstance(kid, str) or not isinstance(encoded, str) or not kid:
                raise ValueError("JWT_SIGNING_KEYS entries must map a kid to base64 text")
            keys[kid] = decode_key(encoded, f"JWT_SIGNING_KEYS[{kid}]")
        return keys

    def code_key(self) -> bytes:
        """Return the decoded one-time-code HMAC key."""
        return decode_key(self.code_hmac_key.get_secret_value(), "CODE_HMAC_KEY")

    def email_key(self) -> bytes:
        """Return the decoded email-hash HMAC key (shadow counters)."""
        return decode_key(self.email_hash_key.get_secret_value(), "EMAIL_HASH_KEY")

    @property
    def refresh_token_ttl_seconds(self) -> int:
        """Refresh-session lifetime in seconds (``REFRESH_TOKEN_DAYS`` x 1 day)."""
        return self.refresh_token_days * SECONDS_PER_DAY

    @property
    def csrf_origins(self) -> list[str]:
        """The CSRF and CORS allow-list: ``CSRF_ALLOWED_ORIGINS`` or ``FRONTEND_ORIGIN``."""
        return list(self.csrf_allowed_origins) or [self.frontend_origin]

    @property
    def is_development(self) -> bool:
        """True only for local development (enables /docs and relaxes HSTS)."""
        return self.app_env == "development"

    @property
    def sqlalchemy_url(self) -> str:
        """The database URL with the psycopg 3 driver selected."""
        url = self.database_url.get_secret_value()
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url.removeprefix("postgresql://")
        return url


class SettingsError(RuntimeError):
    """Configuration is missing or unsafe. The message names settings, never values."""


def load_settings() -> Settings:
    """Load and validate settings, turning validation errors into a safe message.

    Raises:
        SettingsError: Listing each invalid setting by name and the rule it broke.
    """
    try:
        return Settings()  # values come from the environment and .env
    except ValidationError as exc:
        problems = []
        for error in exc.errors(include_input=False, include_url=False):
            name = ".".join(str(part) for part in error["loc"]) or "settings"
            problems.append(f"{name}: {error['msg']}")
        raise SettingsError("Invalid configuration: " + "; ".join(problems)) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process from the environment and ``.env``."""
    return load_settings()
