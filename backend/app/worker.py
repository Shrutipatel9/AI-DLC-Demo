"""The background worker process (composition root; US1.7).

Run it next to the API::

    uv run python -m app.worker

It builds the same settings, database, landmark service and AI adapters as the API, registers
the analysis pipeline as the handler of ``analysis.run`` jobs and polls the ``jobs`` table. It
stops cleanly on SIGINT/SIGTERM (the job in hand finishes first). Jobs a dead worker left
running are resumed or failed by the next worker that starts (AC1.7.2).

Start-up fails fast (non-zero exit) when the settings are invalid, the database is unreachable,
migrations are not at head or the pinned face model is missing.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
from types import FrameType

from app.ai.public import build_text_model
from app.analysis.public import JOB_KIND, build_pipeline
from app.face.public import build_face_geometry
from app.jobs.public import Worker, build_job_queue
from app.measurement.public import build_measurement
from app.media.public import build_media_store
from app.onboarding.public import build_onboarding
from app.platform.clock import SystemClock
from app.platform.db import (
    check_database,
    check_migrations_at_head,
    create_db_engine,
    create_session_factory,
)
from app.platform.logging import configure_logging
from app.platform.settings import Settings, SettingsError, get_settings
from app.report_writing.public import build_report_writing, fake_report

logger = logging.getLogger("worker")


def build_worker(settings: Settings) -> Worker:
    """Wire the worker from settings (the same collaborators the API uses)."""
    clock = SystemClock()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    geometry = build_face_geometry(settings)
    pipeline = build_pipeline(
        settings,
        clock=clock,
        session_factory=session_factory,
        media=build_media_store(settings, clock=clock),
        measurement=build_measurement(settings, geometry=geometry),
        onboarding=build_onboarding(settings, clock=clock),
        report_writing=build_report_writing(
            settings, text_model=build_text_model(settings, responder=fake_report)
        ),
    )
    geometry.load()  # once per process; a missing or wrong model fails start-up
    return Worker(
        queue=build_job_queue(settings, clock=clock),
        session_factory=session_factory,
        handlers={JOB_KIND: pipeline.handle},
        failure_hooks={JOB_KIND: pipeline.on_job_failed},
        heartbeat_seconds=settings.worker_heartbeat_seconds,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the worker until interrupted. Returns the process exit code."""
    parser = argparse.ArgumentParser(
        prog="app.worker", description="Run the background worker (analysis jobs)."
    )
    parser.add_argument(
        "--label",
        default="",
        help="A free-text tag shown in the process list (scripts stop their own worker by it).",
    )
    parser.parse_args(argv)
    try:
        settings = get_settings()
    except SettingsError as error:
        print(str(error), file=sys.stderr)
        return 2
    configure_logging(settings.log_level)
    engine = create_db_engine(settings)
    check_database(engine)
    check_migrations_at_head(engine)
    engine.dispose()
    worker = build_worker(settings)

    stop = threading.Event()

    def request_stop(_signum: int, _frame: FrameType | None) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    worker.run_forever(stop)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
