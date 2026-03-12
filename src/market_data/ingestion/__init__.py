"""Ingestion package — entry points for `uv run ingest` and `uv run scheduler`."""
from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def run_once() -> None:
    """Entry point for `uv run ingest` — runs all interval jobs once and exits."""
    import dotenv
    dotenv.load_dotenv()
    from market_data.db import migrate as _migrate
    _migrate()
    from market_data.ingestion.jobs import run_1d_job, run_1h_job, run_1m_job, run_5m_job

    async def _all() -> None:
        await run_1m_job()
        await run_5m_job()
        await run_1h_job()
        await run_1d_job()

    asyncio.run(_all())


def run_scheduler() -> None:
    """Entry point for `uv run scheduler` — runs the persistent APScheduler loop."""
    from market_data.ingestion.scheduler import run_scheduler as _run
    _run()
