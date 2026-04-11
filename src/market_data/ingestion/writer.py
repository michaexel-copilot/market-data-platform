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
            int(r.ts.timestamp()) // 60 if str(r.interval) == "1m" else None,
            int(r.ts.timestamp()) // 3600 if str(r.interval) == "1h" else None,
            int(r.ts.timestamp()) // 86400 if str(r.interval) == "1d" else None,
            r.is_aggregated,
        )
        for r in records
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO ohlcv
                (instrument_id, interval, ts, open, high, low, close,
                 volume, vwap, trade_count, market_cap, source, ingested_at,
                 tick_1m, tick_1h, tick_1d, is_aggregated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (instrument_id, interval, ts) DO UPDATE SET
                open        = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN excluded.open        ELSE ohlcv.open        END,
                high        = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN excluded.high        ELSE ohlcv.high        END,
                low         = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN excluded.low         ELSE ohlcv.low         END,
                close       = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN excluded.close       ELSE ohlcv.close       END,
                volume      = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN COALESCE(excluded.volume, ohlcv.volume)    ELSE ohlcv.volume      END,
                vwap        = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN COALESCE(excluded.vwap, ohlcv.vwap)        ELSE ohlcv.vwap        END,
                trade_count = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN COALESCE(excluded.trade_count, ohlcv.trade_count) ELSE ohlcv.trade_count END,
                market_cap  = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN COALESCE(excluded.market_cap, ohlcv.market_cap)   ELSE ohlcv.market_cap  END,
                source      = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN excluded.source      ELSE ohlcv.source      END,
                ingested_at = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN excluded.ingested_at ELSE ohlcv.ingested_at END,
                tick_1m     = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN excluded.tick_1m     ELSE ohlcv.tick_1m     END,
                tick_1h     = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN excluded.tick_1h     ELSE ohlcv.tick_1h     END,
                tick_1d     = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                   THEN excluded.tick_1d     ELSE ohlcv.tick_1d     END,
                is_aggregated = CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE
                                     THEN excluded.is_aggregated ELSE ohlcv.is_aggregated END
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
