"""Email dispatch with a bulkhead and a total budget (reliability design section 2, NFR5.13).

- At most ``max_concurrency`` sends run at once (a dedicated AnyIO ``CapacityLimiter``),
  so slow email can never use up the threads that verify, ``/auth/me`` and health need.
- Waiting for a slot counts against the budget; if no slot frees in time the send ends
  as ``UPSTREAM_UNAVAILABLE`` (503).
- Final failures become ``UPSTREAM_TIMEOUT`` (504) or ``UPSTREAM_UNAVAILABLE`` (502).

The limiters belong to the running event loop, so :meth:`EmailDispatcher.start` is called
from the application lifespan.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from functools import partial
from typing import Any

import anyio
import anyio.to_thread

from app.platform.email.port import EmailError, EmailSender, EmailTemplate, EmailTimeoutError
from app.platform.errors import UpstreamTimeout, UpstreamUnavailable
from app.platform.metrics import Metrics
from app.platform.retry import Deadline

logger = logging.getLogger("platform.email")


class EmailDispatcher:
    """Runs blocking email sends in threads, bounded by a bulkhead and a deadline.

    Args:
        sender: The configured :class:`EmailSender`.
        budget_seconds: Total time for one send, including the wait for a slot.
        max_concurrency: Most sends allowed in flight at once.
        metrics: Optional metrics for ``email_send_failures_total``.
    """

    def __init__(
        self,
        sender: EmailSender,
        *,
        budget_seconds: float,
        max_concurrency: int,
        metrics: Metrics | None = None,
    ) -> None:
        self.sender = sender
        self._budget = budget_seconds
        self._max_concurrency = max_concurrency
        self._metrics = metrics
        self._admission: anyio.CapacityLimiter | None = None
        self._threads: anyio.CapacityLimiter | None = None

    @property
    def adapter_name(self) -> str:
        """Name of the configured adapter (for logs)."""
        return str(getattr(self.sender, "adapter_name", type(self.sender).__name__))

    def start(self) -> None:
        """Create the limiters inside the running event loop (called by the lifespan)."""
        self._admission = anyio.CapacityLimiter(self._max_concurrency)
        self._threads = anyio.CapacityLimiter(self._max_concurrency)

    @property
    def in_flight(self) -> int:
        """Sends currently holding a slot."""
        return 0 if self._admission is None else int(self._admission.borrowed_tokens)

    async def send(self, to: str, template: EmailTemplate, variables: Mapping[str, Any]) -> None:
        """Send one email within the budget.

        Raises:
            UpstreamUnavailable: 503 when no slot freed in time; 502 on a final failure.
            UpstreamTimeout: 504 when the provider did not answer in time.
        """
        if self._admission is None or self._threads is None:
            raise RuntimeError("EmailDispatcher.start() must run in the application lifespan")
        started = time.monotonic()
        with anyio.move_on_after(self._budget) as waiting:
            await self._admission.acquire()
        if waiting.cancelled_caught:
            self._record_failure("no_slot")
            raise UpstreamUnavailable(status_code=503)
        try:
            remaining = self._budget - (time.monotonic() - started)
            deadline = Deadline(max(0.0, remaining))
            call = partial(self.sender.send, to, template, variables, deadline=deadline)
            await anyio.to_thread.run_sync(call, limiter=self._threads)
        except EmailTimeoutError as exc:
            self._record_failure("timeout", exc)
            raise UpstreamTimeout() from exc
        except EmailError as exc:
            self._record_failure("error", exc)
            raise UpstreamUnavailable() from exc
        except Exception as exc:
            self._record_failure("unexpected", exc, unexpected=True)
            raise UpstreamUnavailable() from exc
        finally:
            self._admission.release()

    def _record_failure(
        self, reason: str, exc: BaseException | None = None, *, unexpected: bool = False
    ) -> None:
        if self._metrics is not None:
            self._metrics.email_send_failures_total.labels(reason=reason).inc()
        logger.error(
            "email send failed",
            exc_info=unexpected,
            extra={
                "event": "vendor.failed",
                "adapter": self.adapter_name,
                "errorClass": type(exc).__name__ if exc else reason,
            },
        )
