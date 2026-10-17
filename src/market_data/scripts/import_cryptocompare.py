"""import-cryptocompare — import CryptoCompare hourly OHLCV flat files into the platform.

The tool operates in three steps that must be run in order:

1. **stage** — load a CryptoCompare hourly CSV flat file into the staging table
   ``stg_cryptocompare_1h``.  The staged rows keep the CryptoCompare instrument ID
   (e.g. ``BTC-USD``).

2. **migrate** — upsert the staged 1h rows into the production ``ohlcv`` table under the
   *canonical* CoinMarketCap instrument ID (e.g. ``bitcoin``).  The ``--canonical-instrument-id``
   argument is **required** and must match an existing or creatable entry in the
   ``instruments`` table.

3. **aggregate-daily** — derive 1d candles from the staged hourly rows and upsert them into
   ``ohlcv`` under the same canonical instrument ID.  Must be run after ``migrate``.

Usage:
    import-cryptocompare stage [--file FILE] [--instrument-id ID]
    import-cryptocompare migrate [--instrument-id ID] --canonical-instrument-id CANONICAL_ID
    import-cryptocompare aggregate-daily [--instrument-id ID] --canonical-instrument-id CANONICAL_ID

Example (BTC hourly flat file → canonical 'bitcoin' instrument):
    import-cryptocompare stage --file /appdata/cryptocompare/1-hour/bitcoin-hourly-ohlcv.txt
    import-cryptocompare migrate --canonical-instrument-id bitcoin
    import-cryptocompare aggregate-daily --canonical-instrument-id bitcoin
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from market_data.db.connection import get_connection

logger = logging.getLogger(__name__)

_DEFAULT_INSTRUMENT_ID = "BTC-USD"
_DEFAULT_FILE = "/appdata/cryptocompare/1-hour/bitcoin-hourly-ohlcv.txt"
_CRYPTOCOMPARE_SOURCE_ID = 4  # data_source.data_source_id for 'cryptocompare'
_BATCH_SIZE = 5000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_instrument(conn, instrument_id: str) -> None:
    """Insert a minimal instruments row if none exists for instrument_id."""
    ticker = instrument_id.split("-")[0]
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO instruments (instrument_id, ticker, asset_class, is_active)
            VALUES (%s, %s, 'crypto', TRUE)
            ON CONFLICT (instrument_id) DO NOTHING
            """,
            (instrument_id, ticker),
        )


def _upsert_data_available(conn, instrument_id: str, has_1h: bool = False, has_1d: bool = False) -> None:
    """Create or update the ohlcv_data_available row for CryptoCompare."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ohlcv_data_available (instrument_id, data_source_id, has_1m, has_5m, has_1h, has_1d)
            VALUES (%s, %s, FALSE, FALSE, %s, %s)
            ON CONFLICT (instrument_id, data_source_id) DO UPDATE SET
                has_1h = ohlcv_data_available.has_1h OR excluded.has_1h,
                has_1d = ohlcv_data_available.has_1d OR excluded.has_1d
            """,
            (instrument_id, _CRYPTOCOMPARE_SOURCE_ID, has_1h, has_1d),
        )


def _is_valid_ohlcv(open_: float, high: float, low: float, close: float) -> bool:
    return (
        open_ > 0
        and high > 0
        and low > 0
        and close > 0
        and high >= max(open_, close)
        and low <= min(open_, close)
        and low <= high
    )


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_stage(args: argparse.Namespace) -> None:
    """Load a CryptoCompare hourly CSV file into stg_cryptocompare_1h."""
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    instrument_id = args.instrument_id
    conn = get_connection()

    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM stg_cryptocompare_1h WHERE instrument_id = %s",
            (instrument_id,),
        )

    rows = []
    skipped_invalid = 0
    with file_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            unix_ts = int(row["UNIX_TIMESTAMP"])
            volume_usd = row.get("VOLUME_USD", "").strip()
            volume_btc = row.get("VOLUME_BTC", "").strip()
            open_ = float(row["OPEN"])
            high = float(row["HIGH"])
            close = float(row["CLOSE"])
            low = float(row["LOW"])
            if not _is_valid_ohlcv(open_, high, low, close):
                skipped_invalid += 1
                continue
            rows.append((
                instrument_id,
                unix_ts,
                datetime.fromtimestamp(unix_ts, tz=timezone.utc),
                open_,
                high,
                close,
                low,
                float(volume_usd) if volume_usd else None,
                float(volume_btc) if volume_btc else None,
            ))

    total = 0
    with conn.cursor() as cur:
        for i in range(0, len(rows), _BATCH_SIZE):
            batch = rows[i : i + _BATCH_SIZE]
            cur.executemany(
                """
                INSERT INTO stg_cryptocompare_1h
                    (instrument_id, unix_timestamp, datetime, open, high, close, low,
                     volume_usd, volume_btc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (instrument_id, unix_timestamp) DO NOTHING
                """,
                batch,
            )
            total += len(batch)

    print(f"Staged {total} rows for {instrument_id}; skipped {skipped_invalid} invalid row(s)")


def cmd_migrate(args: argparse.Namespace) -> None:
    """Upsert staged 1h rows from stg_cryptocompare_1h into production ohlcv."""
    staged_instrument_id = args.instrument_id
    canonical_instrument_id = args.canonical_instrument_id
    conn = get_connection()

    _ensure_instrument(conn, canonical_instrument_id)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ohlcv
                (instrument_id, interval, ts, open, high, low, close,
                 volume, vwap, trade_count, market_cap, source, ingested_at,
                 tick_1h)
            SELECT
                %s,
                '1h',
                datetime,
                open,
                high,
                low,
                close,
                volume_usd,
                NULL,
                NULL,
                NULL,
                'cryptocompare',
                NOW(),
                EXTRACT(EPOCH FROM datetime)::BIGINT / 3600
            FROM stg_cryptocompare_1h
            WHERE instrument_id = %s
            ON CONFLICT (instrument_id, interval, ts) DO UPDATE SET
                open        = excluded.open,
                high        = excluded.high,
                low         = excluded.low,
                close       = excluded.close,
                volume      = COALESCE(excluded.volume, ohlcv.volume),
                source      = excluded.source,
                ingested_at = excluded.ingested_at,
                tick_1h     = excluded.tick_1h
            """,
            (canonical_instrument_id, staged_instrument_id),
        )
        row_count = cur.rowcount

    _upsert_data_available(conn, canonical_instrument_id, has_1h=True)
    print(f"Migrated {row_count} hourly rows for {canonical_instrument_id}")


def cmd_aggregate_daily(args: argparse.Namespace) -> None:
    """Derive 1d candles from stg_cryptocompare_1h and upsert into production ohlcv."""
    staged_instrument_id = args.instrument_id
    canonical_instrument_id = args.canonical_instrument_id
    conn = get_connection()

    _ensure_instrument(conn, canonical_instrument_id)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ohlcv
                (instrument_id, interval, ts, open, high, low, close,
                 volume, vwap, trade_count, market_cap, source, ingested_at,
                 tick_1d)
            SELECT
                %s,
                '1d',
                DATE_TRUNC('day', datetime)::timestamptz                     AS ts,
                (ARRAY_AGG(open  ORDER BY datetime ASC))[1]                  AS open,
                MAX(high)                                                     AS high,
                MIN(low)                                                      AS low,
                (ARRAY_AGG(close ORDER BY datetime DESC))[1]                 AS close,
                SUM(volume_usd)                                               AS volume,
                NULL,
                NULL,
                NULL,
                'cryptocompare',
                NOW(),
                EXTRACT(EPOCH FROM DATE_TRUNC('day', datetime))::BIGINT / 86400
            FROM stg_cryptocompare_1h
            WHERE instrument_id = %s
            GROUP BY DATE_TRUNC('day', datetime)
            ON CONFLICT (instrument_id, interval, ts) DO UPDATE SET
                open        = excluded.open,
                high        = excluded.high,
                low         = excluded.low,
                close       = excluded.close,
                volume      = COALESCE(excluded.volume, ohlcv.volume),
                source      = excluded.source,
                ingested_at = excluded.ingested_at,
                tick_1d     = excluded.tick_1d
            """,
            (canonical_instrument_id, staged_instrument_id),
        )
        row_count = cur.rowcount

    _upsert_data_available(conn, canonical_instrument_id, has_1d=True)
    print(f"Upserted {row_count} daily rows for {canonical_instrument_id}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(
        description="Import CryptoCompare hourly OHLCV flat files into the platform."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # stage
    p_stage = sub.add_parser("stage", help="Load CSV flat file into staging table")
    p_stage.add_argument(
        "--instrument-id",
        default=_DEFAULT_INSTRUMENT_ID,
        help=f"Instrument ID to tag all rows with (default: {_DEFAULT_INSTRUMENT_ID})",
    )
    p_stage.add_argument(
        "--file",
        default=_DEFAULT_FILE,
        help=f"Path to the CryptoCompare hourly CSV file (default: {_DEFAULT_FILE})",
    )
    p_stage.set_defaults(func=cmd_stage)

    # migrate
    p_migrate = sub.add_parser("migrate", help="Upsert staged 1h rows into production ohlcv")
    p_migrate.add_argument(
        "--instrument-id",
        default=_DEFAULT_INSTRUMENT_ID,
        help=f"Staged instrument ID in stg_cryptocompare_1h (default: {_DEFAULT_INSTRUMENT_ID})",
    )
    p_migrate.add_argument(
        "--canonical-instrument-id",
        required=True,
        help="Canonical instrument ID to use in ohlcv (e.g. 'bitcoin' from CoinMarketCap)",
    )
    p_migrate.set_defaults(func=cmd_migrate)

    # aggregate-daily
    p_agg = sub.add_parser("aggregate-daily", help="Derive and upsert 1d candles from staging")
    p_agg.add_argument(
        "--instrument-id",
        default=_DEFAULT_INSTRUMENT_ID,
        help=f"Staged instrument ID in stg_cryptocompare_1h (default: {_DEFAULT_INSTRUMENT_ID})",
    )
    p_agg.add_argument(
        "--canonical-instrument-id",
        required=True,
        help="Canonical instrument ID to use in ohlcv (e.g. 'bitcoin' from CoinMarketCap)",
    )
    p_agg.set_defaults(func=cmd_aggregate_daily)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
