"""APScheduler-based ingestion scheduler."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from market_data.ingestion.jobs import run_1d_job, run_1h_job, run_1m_job, run_5m_job

logger = logging.getLogger(__name__)

# Registry: job_id → (coroutine_function, trigger_factory)
# trigger_factory is a zero-argument callable that returns a fresh trigger.
_JOB_REGISTRY: dict[str, tuple[Callable, Callable]] = {
    "ohlcv_1m": (run_1m_job, lambda: IntervalTrigger(minutes=1)),
    "ohlcv_5m": (run_5m_job, lambda: IntervalTrigger(minutes=5)),
    "ohlcv_1h": (run_1h_job, lambda: CronTrigger(minute=0)),
    "ohlcv_1d": (run_1d_job, lambda: CronTrigger(hour=0, minute=5)),
}

# Module-level singleton set by _run_async / the API serve path.
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler | None:
    """Return the running scheduler instance, or None if not started."""
    return _scheduler


def build_scheduler(enabled_jobs: set[str] | None = None) -> AsyncIOScheduler:
    """Create and configure the APScheduler instance.

    Args:
        enabled_jobs: Set of job IDs to register.  ``None`` (default) registers
                      all jobs — preserves backward-compat for callers that don't
                      supply DB state.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    for job_id, (func, trigger_factory) in _JOB_REGISTRY.items():
        if enabled_jobs is None or job_id in enabled_jobs:
            scheduler.add_job(
                func,
                trigger=trigger_factory(),
                id=job_id,
                max_instances=1,
                coalesce=True,
            )

    return scheduler


def run_scheduler() -> None:
    """Entry point for `uv run scheduler` — runs the scheduler in an event loop."""
    import dotenv
    dotenv.load_dotenv()
    from market_data.db import migrate
    migrate()

    asyncio.run(_run_async())


async def _run_async() -> None:
    global _scheduler

    from market_data.db.connection import get_connection
    from market_data.db.scheduler_jobs import load_job_states

    conn = get_connection()
    states = load_job_states(conn)
    enabled = {job_id for job_id, enabled in states.items() if enabled}

    _scheduler = build_scheduler(enabled_jobs=enabled)
    _scheduler.start()
    logger.info("Scheduler started — running ingestion jobs")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down")
        _scheduler.shutdown(wait=False)
