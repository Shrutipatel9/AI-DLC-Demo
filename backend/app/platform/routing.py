"""Route classes (security design section 1, NFR2.8).

Secure by default: every router is mounted with the ``current_user`` dependency. Only
the paths below are exempt, and a start-up assertion plus the route-enumeration test
keep this list honest.
"""

from __future__ import annotations

from collections.abc import Iterable

#: Paths that need no access token. ``/auth/refresh`` and ``/auth/logout`` are
#: authenticated by the refresh cookie and guarded by the CSRF check instead (U2).
PUBLIC_ROUTES: frozenset[str] = frozenset(
    {
        "/health",
        "/health/ready",
        "/auth/register",
        "/auth/login",
        "/auth/verify",
        "/auth/resend-code",
        "/auth/refresh",
        "/auth/logout",
        "/auth/password/forgot",
        "/auth/password/verify-code",
        "/auth/password/reset",
        # Authenticated by the provider's signature over the raw body (contract C2, U5).
        "/payments/stripe/webhook",
    }
)

#: Enabled only when APP_ENV=development.
DEV_ONLY_ROUTES: frozenset[str] = frozenset({"/docs", "/docs/oauth2-redirect", "/openapi.json"})

#: Token-exempt operational routes with their own guard (metrics CIDR allow-list).
OPERATIONAL_ROUTES: frozenset[str] = frozenset({"/metrics"})


#: The fake payment provider's hosted test page (U5): mounted only with
#: ``PAYMENT_PROVIDER=fake``, which settings refuse outside development and test.
FAKE_PAYMENT_ROUTES: frozenset[str] = frozenset(
    {
        "/payments/fake-checkout/{session_id}",
        "/payments/fake-checkout/{session_id}/pay",
        "/payments/fake-checkout/{session_id}/cancel",
    }
)


class RouteClassError(RuntimeError):
    """The public router does not match ``PUBLIC_ROUTES`` exactly."""


def assert_public_routes(paths: Iterable[str]) -> None:
    """Fail start-up unless the public router serves exactly ``PUBLIC_ROUTES``.

    Raises:
        RouteClassError: Naming any missing or unexpected public path.
    """
    actual = frozenset(paths)
    if actual != PUBLIC_ROUTES:
        missing = sorted(PUBLIC_ROUTES - actual)
        extra = sorted(actual - PUBLIC_ROUTES)
        raise RouteClassError(f"Public routes mismatch: missing={missing}, unexpected={extra}")


def assert_fake_payment_routes(paths: Iterable[str]) -> None:
    """Fail start-up unless the fake provider's router serves exactly ``FAKE_PAYMENT_ROUTES``.

    Raises:
        RouteClassError: Naming any missing or unexpected path.
    """
    actual = frozenset(paths)
    if actual != FAKE_PAYMENT_ROUTES:
        missing = sorted(FAKE_PAYMENT_ROUTES - actual)
        extra = sorted(actual - FAKE_PAYMENT_ROUTES)
        raise RouteClassError(
            f"Fake payment routes mismatch: missing={missing}, unexpected={extra}"
        )
