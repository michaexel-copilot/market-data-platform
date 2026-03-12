"""Ingestion jobs — per-interval async fetch-and-write tasks."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from market_data.connectors import registry
from market_data.db.connection import get_connection
from market_data.ingestion.writer import write_ohlcv
from market_data.models.enums import Interval

logger = logging.getLogger(__name__)

# How far back each job looks when catching up after a restart
_LOOKBACK: dict[Interval, timedelta] = {
    Interval.ONE_MIN:  timedelta(minutes=5),
    Interval.FIVE_MIN: timedelta(minutes=30),
    Interval.ONE_HOUR: timedelta(hours=4),
    Interval.ONE_DAY:  timedelta(days=3),
}


def _active_instrument_ids() -> list[str]:
    """Return instrument_ids for all active instruments tracked in DuckDB."""
    conn = get_connection()
    rows = conn.execute("SELECT instrument_id FROM instruments WHERE is_active = TRUE").fetchall()
    return [r[0] for r in rows]


async def _run_interval_job(interval: Interval) -> None:
    until = datetime.now(tz=timezone.utc)
    since = until - _LOOKBACK[interval]
    connectors = registry.for_interval(interval)
    instrument_ids = _active_instrument_ids()
    if not instrument_ids:
        logger.debug("No active instruments — skipping %s job", interval)
        return

    for instrument_id in instrument_ids:
        for conn in connectors:
            try:
                records = await conn.fetch_ohlcv(instrument_id, interval, since, until)
                if records:
                    written = write_ohlcv(records)
                    logger.debug(
                        "[%s] %s via %s: %d records",
                        interval,
                        instrument_id,
                        conn.name,
                        written,
                    )
            except NotImplementedError:
                pass
            except Exception as exc:
                logger.warning(
                    "[%s] %s via %s failed: %s",
                    interval,
                    instrument_id,
                    conn.name,
                    exc,
                )


async def run_1m_job() -> None:
    """Fetch and persist 1-minute OHLCV data for all active instruments."""
    await _run_interval_job(Interval.ONE_MIN)


async def run_5m_job() -> None:
    """Fetch and persist 5-minute OHLCV data for all active instruments."""
    await _run_interval_job(Interval.FIVE_MIN)


async def run_1h_job() -> None:
    """Fetch and persist 1-hour OHLCV data for all active instruments."""
    await _run_interval_job(Interval.ONE_HOUR)


async def run_1d_job() -> None:
    """Fetch and persist 1-day OHLCV data for all active instruments."""
    await _run_interval_job(Interval.ONE_DAY)
