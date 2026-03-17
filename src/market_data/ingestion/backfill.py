"""Backfill — historical OHLCV data population for a given source/asset/interval."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from market_data.connectors import registry
from market_data.ingestion.writer import write_ohlcv
from market_data.models.enums import AssetClass, Interval

logger = logging.getLogger(__name__)


async def backfill(
    source: str,
    asset_class: AssetClass,
    interval: Interval,
    since: datetime,
    until: datetime | None = None,
    instrument_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch historical OHLCV data from *source* and persist to DuckDB.

    Args:
        source: Connector name (e.g. ``"binance"``, ``"eodhd"``).
        asset_class: Asset class to backfill.
        interval: OHLCV interval.
        since: Start of the historical range (UTC).
        until: End of the historical range (defaults to now).
        instrument_ids: Optional explicit list of instrument IDs. When *None*,
            backfills all active instruments of the given asset class.

    Returns:
        A summary dict with ``total_written`` and ``errors`` counts.
    """
    if until is None:
        until = datetime.now(tz=timezone.utc)

    conn = registry.get(source)
    if conn is None:
        raise ValueError(f"Unknown connector: {source!r}")

    if instrument_ids is None:
        from market_data.db.connection import get_connection as _gc
        db = _gc()
        rows = db.execute(
            "SELECT instrument_id FROM instruments WHERE asset_class = %s AND is_active = TRUE",
            [str(asset_class)],
        ).fetchall()
        instrument_ids = [r[0] for r in rows]

    total_written = 0
    errors = 0
    for instrument_id in instrument_ids:
        try:
            records = await conn.fetch_ohlcv(instrument_id, interval, since, until)
            if records:
                written = write_ohlcv(records)
                total_written += written
                logger.info("Backfill %s %s %s: %d records", source, instrument_id, interval, written)
        except Exception as exc:
            logger.warning("Backfill error %s %s: %s", source, instrument_id, exc)
            errors += 1

    return {"total_written": total_written, "errors": errors}


def run_backfill_cli() -> None:
    """CLI entry point — parse args and run the backfill coroutine."""
    import argparse

    parser = argparse.ArgumentParser(description="Backfill historical OHLCV data")
    parser.add_argument("--source", required=True, help="Connector name")
    parser.add_argument("--asset-class", required=True, choices=[a.value for a in AssetClass])
    parser.add_argument("--interval", required=True, choices=[i.value for i in Interval if i.is_native])
    parser.add_argument("--since", required=True, help="ISO 8601 start date")
    parser.add_argument("--until", help="ISO 8601 end date (default: now)")
    parser.add_argument("--instruments", nargs="*", help="Optional instrument IDs")
    args = parser.parse_args()

    import dotenv
    dotenv.load_dotenv()

    since_dt = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    until_dt = datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc) if args.until else None

    summary = asyncio.run(
        backfill(
            source=args.source,
            asset_class=AssetClass(args.asset_class),
            interval=Interval(args.interval),
            since=since_dt,
            until=until_dt,
            instrument_ids=args.instruments,
        )
    )
    print(f"Backfill complete: {summary}")
