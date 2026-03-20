"""APScheduler-based ingestion scheduler."""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from market_data.ingestion.jobs import run_1d_job, run_1h_job, run_1m_job, run_5m_job

logger = logging.getLogger(__name__)


def build_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        run_1m_job,
        trigger=IntervalTrigger(minutes=1),
        id="ohlcv_1m",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_5m_job,
        trigger=IntervalTrigger(minutes=5),
        id="ohlcv_5m",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_1h_job,
        trigger=CronTrigger(minute=0),  # top of each hour
        id="ohlcv_1h",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_1d_job,
        trigger=CronTrigger(hour=0, minute=5),  # 00:05 UTC daily
        id="ohlcv_1d",
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
    scheduler = build_scheduler()
    scheduler.start()
    logger.info("Scheduler started — running ingestion jobs")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down")
        scheduler.shutdown(wait=False)
