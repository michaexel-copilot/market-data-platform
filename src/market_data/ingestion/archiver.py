"""Archiver — moves aged 1m/5m OHLCV rows to Parquet and removes them from live table."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from market_data.db.connection import get_connection

logger = logging.getLogger(__name__)

_ARCHIVE_DIR = Path(os.getenv("ARCHIVE_DIR", "archive"))
_RETENTION_DAYS = int(os.getenv("ARCHIVE_RETENTION_DAYS", "90"))
_INTERVALS_TO_ARCHIVE = ("1m", "5m")


def archive_old_ohlcv() -> dict[str, int]:
    """Export rows older than *retention* days to Parquet, then delete from the database.

    Returns:
        Dict mapping interval → number of rows archived.
    """
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=_RETENTION_DAYS)
    summary: dict[str, int] = {}

    for interval in _INTERVALS_TO_ARCHIVE:
        parquet_path = _ARCHIVE_DIR / f"ohlcv_{interval}_{cutoff.strftime('%Y%m%d')}.parquet"
        try:
            conn.execute(
                f"""
                COPY (
                    SELECT * FROM ohlcv
                    WHERE interval = ? AND ts < ?
                    ORDER BY ts
                ) TO '{parquet_path}' (FORMAT PARQUET)
                """,
                [interval, cutoff],
            )
            count_rows = conn.execute(
                "SELECT COUNT(*) FROM ohlcv WHERE interval = ? AND ts < ?",
                [interval, cutoff],
            ).fetchone()
            count = count_rows[0] if count_rows else 0
            conn.execute(
                "DELETE FROM ohlcv WHERE interval = ? AND ts < ?",
                [interval, cutoff],
            )
            summary[interval] = count
            logger.info(
                "Archived %d %s rows to %s and removed from live table",
                count,
                interval,
                parquet_path,
            )
        except Exception as exc:
            logger.error("Archive failed for interval %s: %s", interval, exc)
            summary[interval] = -1

    return summary
