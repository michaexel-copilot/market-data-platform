"""Ingestion writer — persists OHLCV records and instrument records to PostgreSQL."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from market_data.db.connection import get_connection
from market_data.models.instrument import InstrumentRecord
from market_data.models.ohlcv import OHLCVRecord

logger = logging.getLogger(__name__)


def write_ohlcv(records: list[OHLCVRecord]) -> int:
    """Upsert OHLCV records into the ``ohlcv`` table.

    Uses ``INSERT … ON CONFLICT DO UPDATE`` upsert semantics.

    Returns:
        Number of rows written.
    """
    if not records:
        return 0
    conn = get_connection()
    now = datetime.now(tz=timezone.utc)
    rows = [
        (
            r.instrument_id,
            str(r.interval),
            r.ts,
            r.open,
            r.high,
            r.low,
            r.close,
            r.volume,
            r.vwap,
            r.trade_count,
            r.market_cap,
            r.source,
            now,
        )
        for r in records
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO ohlcv
                (instrument_id, interval, ts, open, high, low, close,
                 volume, vwap, trade_count, market_cap, source, ingested_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (instrument_id, interval, ts) DO UPDATE SET
                open       = excluded.open,
                high       = excluded.high,
                low        = excluded.low,
                close      = excluded.close,
                volume     = COALESCE(excluded.volume, ohlcv.volume),
                vwap       = COALESCE(excluded.vwap, ohlcv.vwap),
                trade_count = COALESCE(excluded.trade_count, ohlcv.trade_count),
                market_cap  = COALESCE(excluded.market_cap, ohlcv.market_cap),
                source      = excluded.source,
                ingested_at = excluded.ingested_at
            """,
            rows,
        )
    logger.debug("Wrote %d OHLCV records", len(rows))
    return len(rows)


def write_instruments(records: list[InstrumentRecord]) -> int:
    """Upsert instrument records into the ``instruments`` table.

    Returns:
        Number of rows written.
    """
    if not records:
        return 0
    conn = get_connection()
    now = datetime.now(tz=timezone.utc)
    rows = [
        (
            r.instrument_id,
            r.ticker,
            r.full_name,
            r.description,
            str(r.asset_class),
            r.exchange,
            r.sector,
            r.industry,
            r.quote_currency,
            r.launch_date,
            r.is_active,
            r.logo_url,
            r.website_url,
            now,
        )
        for r in records
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO instruments
                (instrument_id, ticker, full_name, description, asset_class, exchange,
                 sector, industry, quote_currency, launch_date, is_active, logo_url,
                 website_url, last_updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (instrument_id) DO UPDATE SET
                ticker           = excluded.ticker,
                full_name        = COALESCE(excluded.full_name, instruments.full_name),
                asset_class      = excluded.asset_class,
                exchange         = COALESCE(excluded.exchange, instruments.exchange),
                is_active        = excluded.is_active,
                last_updated_at  = excluded.last_updated_at
            """,
            rows,
        )
    logger.debug("Wrote %d instrument records", len(rows))
    return len(rows)
