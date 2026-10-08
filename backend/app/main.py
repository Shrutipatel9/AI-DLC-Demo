"""Application factory and lifespan (composition root).

Run locally::

    uvicorn app.main:app --reload --port 8000

(``uvicorn app.main:create_app --factory`` also works.)

Start-up (lifespan) fails fast, and the process exits non-zero, when the settings are
invalid, the database is unreachable, migrations are not at head (NFR5.5), or the pinned
face model is missing (U4, ``FACE_MODEL_PRELOAD``).

Route classes (NFR2.8): one public router holds exactly ``PUBLIC_ROUTES`` (asserted at
start-up); every other router is mounted with ``current_user``; ``/docs`` and
``/openapi.json`` exist only in development; ``/metrics`` is an opt-in sub-app with its
own CIDR guard; the analysis, journey and settings routes are protected like the rest, and the
analysis itself runs in the separate worker process (``python -m app.worker``); the fake
payment provider's test page (``FAKE_PAYMENT_ROUTES``) exists only with ``PAYMENT_PROVIDER=fake``,
which settings allow in development and test only.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import Engine
from starlette.routing import BaseRoute

from app.ai.public import build_text_model
from app.analysis.public import build_analysis, media_in_use
from app.analysis.public import router as analysis_router
from app.chat.public import build_chat
from app.chat.public import router as chat_router
from app.face.public import FaceGeometry, build_face_geometry
from app.health.routes import router as health_router
from app.identity.public import build_identity, current_user, protected_router, public_router
from app.images.public import build_image_generation
from app.images.public import router as images_router
from app.jobs.public import build_job_queue
from app.journey.public import build_journey
from app.journey.public import router as journey_router
from app.media.public import build_media_store
from app.media.public import router as media_router
from app.onboarding.public import build_onboarding
from app.onboarding.public import router as onboarding_router
from app.payments.public import (
    PaymentGateway,
    build_payment_gateway,
    build_payments,
    fake_checkout_router,
    webhook_router,
)
from app.payments.public import router as payments_router
from app.photos.public import build_photos, check_identity
from app.photos.public import router as photos_router
from app.platform.clock import Clock, SystemClock
from app.platform.db import (
    SessionFactory,
    check_database,
    check_migrations_at_head,
    create_db_engine,
    create_session_factory,
    upgrade_to_head,
)
from app.platform.email import build_email_sender
from app.platform.email.dispatch import EmailDispatcher
from app.platform.email.port import EmailSender
from app.platform.errors import install_exception_handlers
from app.platform.logging import configure_logging
from app.platform.metrics import Metrics, MetricsEndpoint
from app.platform.middleware import install_middleware
from app.platform.ratelimit import InMemoryRateLimiter, PostgresRateLimiter, RateLimiter
from app.platform.routing import assert_fake_payment_routes, assert_public_routes
from app.platform.settings import Settings, get_settings
from app.report.public import build_report
from app.report.public import router as report_router
from app.settings.public import router as settings_router

logger = logging.getLogger("app")

API_TITLE = "AI Facial Analysis Platform API"
API_VERSION = "1.0.0"


def route_paths(routes: Iterable[BaseRoute]) -> list[str]:
    """Flatten route paths, including routers nested with ``include_router``."""
    paths: list[str] = []
    for route in routes:
        nested = getattr(route, "original_router", None)
        if nested is not None:
            paths.extend(route_paths(nested.routes))
        elif isinstance(getattr(route, "path", None), str):
            paths.append(route.path)  # type: ignore[attr-defined]
    return paths


def _build_limiter(
    settings: Settings, session_factory: SessionFactory, clock: Clock
) -> RateLimiter:
    if settings.rate_limit_backend == "memory":
        return InMemoryRateLimiter(clock)
    return PostgresRateLimiter(session_factory, clock)


def create_app(
    settings: Settings | None = None,
    *,
    clock: Clock | None = None,
    email_sender: EmailSender | None = None,
    engine: Engine | None = None,
    session_factory: SessionFactory | None = None,
    rate_limiter: RateLimiter | None = None,
    face_geometry: FaceGeometry | None = None,
    payment_gateway: PaymentGateway | None = None,
) -> FastAPI:
    """Build the API. Every collaborator can be injected (tests do this).

    Args:
        settings: Configuration; loaded from the environment when omitted.
        clock: Time source; the system clock by default.
        email_sender: Email adapter; chosen by ``EMAIL_BACKEND`` by default.
        engine: Database engine; created from settings by default.
        session_factory: Session factory; bound to ``engine`` by default.
        rate_limiter: Limiter; chosen by ``RATE_LIMIT_BACKEND`` by default.
        face_geometry: Face landmark service; the pinned MediaPipe model by default.
        payment_gateway: Payment provider adapter; chosen by ``PAYMENT_PROVIDER`` by default.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    clock = clock or SystemClock()
    owns_engine = engine is None
    engine = engine or create_db_engine(settings)
    session_factory = session_factory or create_session_factory(engine)
    metrics = Metrics()
    dispatcher = EmailDispatcher(
        email_sender or build_email_sender(settings),
        budget_seconds=settings.email_send_budget_seconds,
        max_concurrency=settings.email_max_concurrency,
        metrics=metrics,
    )
    limiter = rate_limiter or _build_limiter(settings, session_factory, clock)
    identity = build_identity(
        settings,
        clock=clock,
        dispatcher=dispatcher,
        limiter=limiter,
        metrics=metrics,
        session_factory=session_factory,
    )
    onboarding = build_onboarding(settings, clock=clock)
    media = build_media_store(settings, clock=clock)
    geometry = face_geometry or build_face_geometry(settings)
    photos = build_photos(settings, clock=clock, media=media, geometry=geometry)
    gateway = payment_gateway or build_payment_gateway(settings)
    payments = build_payments(
        settings,
        clock=clock,
        gateway=gateway,
        identity_check=lambda session, user_id: check_identity(photos, session, user_id),
    )

    queue = build_job_queue(settings, clock=clock)
    analysis = build_analysis(settings, clock=clock, queue=queue, payments=payments, photos=photos)
    images = build_image_generation(
        settings, clock=clock, session_factory=session_factory, media=media
    )
    report = build_report(payments=payments, media=media, clock=clock)
    journey = build_journey(onboarding=onboarding, photos=photos, payments=payments)
    chat = build_chat(
        settings,
        text_model=build_text_model(
            settings.model_copy(update={"ai_text_timeout_seconds": settings.chat_timeout_seconds})
        ),
        payments=payments,
        onboarding=onboarding,
        clock=clock,
    )
    # A run keeps the photo files it started with: a retake must not delete them (R-02).
    media.add_reference_check(media_in_use)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if settings.check_migrations_at_startup:
            check_database(engine)
            if settings.db_auto_migrate and settings.app_env == "development":
                upgrade_to_head(settings.database_url.get_secret_value())
            check_migrations_at_head(engine)
        if settings.face_model_preload:
            geometry.load()  # once per process; a missing or wrong model fails start-up
        dispatcher.start()
        logger.info("api started", extra={"event": "app.started"})
        try:
            yield
        finally:
            if owns_engine:
                engine.dispose()

    dev = settings.is_development
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        docs_url="/docs" if dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if dev else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.clock = clock
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.metrics = metrics
    app.state.rate_limiter = limiter
    app.state.email_dispatcher = dispatcher
    app.state.identity = identity
    app.state.onboarding = onboarding
    app.state.media = media
    app.state.face_geometry = geometry
    app.state.photos = photos
    app.state.payment_gateway = gateway
    app.state.payments = payments
    app.state.job_queue = queue
    app.state.analysis = analysis
    app.state.images = images
    app.state.report = report
    app.state.journey = journey
    app.state.chat = chat

    install_exception_handlers(app)
    install_middleware(app, settings, metrics)

    public = APIRouter()
    public.include_router(health_router)
    public.include_router(public_router)
    public.include_router(webhook_router)
    assert_public_routes(route_paths(public.routes))
    app.include_router(public)
    app.include_router(protected_router, dependencies=[Depends(current_user)])
    app.include_router(onboarding_router, dependencies=[Depends(current_user)])
    app.include_router(photos_router, dependencies=[Depends(current_user)])
    app.include_router(media_router, dependencies=[Depends(current_user)])
    app.include_router(payments_router, dependencies=[Depends(current_user)])
    app.include_router(analysis_router, dependencies=[Depends(current_user)])
    app.include_router(images_router, dependencies=[Depends(current_user)])
    app.include_router(report_router, dependencies=[Depends(current_user)])
    app.include_router(journey_router, dependencies=[Depends(current_user)])
    app.include_router(chat_router, dependencies=[Depends(current_user)])
    app.include_router(settings_router, dependencies=[Depends(current_user)])
    if settings.payment_provider == "fake":
        # Development/test only (settings refuse the fake elsewhere): the browser navigates
        # to the fake's hosted page as it would to Stripe's, so it takes no access token.
        assert_fake_payment_routes(route_paths(fake_checkout_router.routes))
        app.include_router(fake_checkout_router)

    if settings.metrics_enabled:
        app.mount("/metrics", MetricsEndpoint(metrics, settings.metrics_allow_cidrs))
    return app


def __getattr__(name: str) -> FastAPI:
    """Expose ``app`` for ``uvicorn app.main:app``, built from the settings on first access.

    Built lazily (PEP 562) so importing this module stays free of side effects; tests and
    tools keep calling ``create_app()`` with their own settings.
    """
    if name == "app":
        application = create_app()
        globals()["app"] = application
        return application
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
