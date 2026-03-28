"""import-kraken-1h — import Kraken historical 1h OHLCV flat files into the platform.

The Kraken CSV format is headerless:
    unix_timestamp, open, high, low, close, volume, trade_count

Usage:
    import-kraken-1h --symbol ADA [--data-dir /mnt/ds420/data/kraken/1-hour]

The pair filename is resolved as follows:
  1. Look up instrument_id in config/kraken_pairs.yaml (exceptions list).
  2. Otherwise, use {TICKER}USD (e.g. ADA → ADAUSD_60.csv).
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from market_data.db.connection import get_connection
from market_data.db.resolver import resolve_symbol
from market_data.models.api import SymbolNotFoundError

_KRAKEN_SOURCE_ID = 5
_BATCH_SIZE = 5000
_DEFAULT_DATA_DIR = "/mnt/ds420/data/kraken/1-hour"
_PAIRS_YAML = Path(__file__).parent.parent / "config" / "kraken_pairs.yaml"


# ---------------------------------------------------------------------------
# Pair resolution
# ---------------------------------------------------------------------------

def _load_pair_overrides() -> dict[str, str]:
    if _PAIRS_YAML.exists():
        with _PAIRS_YAML.open() as fh:
            return yaml.safe_load(fh) or {}
    return {}


def resolve_kraken_pair(instrument_id: str, ticker: str) -> str:
    """Return the Kraken pair prefix for the given instrument.

    Checks config/kraken_pairs.yaml for overrides; falls back to {TICKER}USD.
    """
    overrides = _load_pair_overrides()
    if instrument_id in overrides:
        return overrides[instrument_id]
    return f"{ticker.upper()}USD"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_ticker(instrument_id: str) -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT ticker FROM instruments WHERE instrument_id = %s",
        [instrument_id],
    ).fetchone()
    return row[0] if row else instrument_id.upper()


def _upsert_data_available(conn: Any, instrument_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ohlcv_data_available (instrument_id, data_source_id, has_1m, has_5m, has_1h, has_1d)
            VALUES (%s, %s, FALSE, FALSE, TRUE, FALSE)
            ON CONFLICT (instrument_id, data_source_id) DO UPDATE SET
                has_1h = TRUE
            """,
            (instrument_id, _KRAKEN_SOURCE_ID),
        )


# ---------------------------------------------------------------------------
# Core import
# ---------------------------------------------------------------------------

def import_kraken_1h(instrument_id: str, file_path: Path) -> dict:
    """Parse CSV and upsert 1h rows into ohlcv.

    Returns a dict with keys: rows_inserted, gap_closed_from, gap_closed_to.
    """
    rows: list[tuple] = []
    with file_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if len(row) < 6:
                continue
            unix_ts = int(row[0])
            ts = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
            open_ = float(row[1])
            high = float(row[2])
            low = float(row[3])
            close = float(row[4])
            volume = float(row[5])
            trade_count = int(row[6]) if len(row) > 6 and row[6].strip() else None
            rows.append((
                instrument_id,
                ts,
                open_,
                high,
                low,
                close,
                volume,
                trade_count,
                unix_ts // 3600,  # tick_1h
            ))

    if not rows:
        return {"rows_inserted": 0, "gap_closed_from": None, "gap_closed_to": None}

    conn = get_connection()
    total = 0
    with conn.cursor() as cur:
        for i in range(0, len(rows), _BATCH_SIZE):
            batch = rows[i : i + _BATCH_SIZE]
            cur.executemany(
                """
                INSERT INTO ohlcv
                    (instrument_id, interval, ts, open, high, low, close,
                     volume, trade_count, source, ingested_at, is_aggregated, tick_1h)
                VALUES (%s, '1h', %s, %s, %s, %s, %s, %s, %s, 'kraken', NOW(), FALSE, %s)
                ON CONFLICT (instrument_id, interval, ts) DO UPDATE SET
                    open        = excluded.open,
                    high        = excluded.high,
                    low         = excluded.low,
                    close       = excluded.close,
                    volume      = COALESCE(excluded.volume, ohlcv.volume),
                    trade_count = COALESCE(excluded.trade_count, ohlcv.trade_count),
                    source      = excluded.source,
                    ingested_at = excluded.ingested_at,
                    tick_1h     = excluded.tick_1h
                """,
                batch,
            )
            total += len(batch)

    _upsert_data_available(conn, instrument_id)

    return {
        "rows_inserted": total,
        "gap_closed_from": rows[0][1].isoformat(),
        "gap_closed_to": rows[-1][1].isoformat(),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import Kraken historical 1h OHLCV flat files into the platform."
    )
    parser.add_argument(
        "--symbol",
        required=True,
        help="HL/CMC ticker symbol (e.g. ADA)",
    )
    parser.add_argument(
        "--data-dir",
        default=_DEFAULT_DATA_DIR,
        help=f"Directory containing Kraken _60.csv files (default: {_DEFAULT_DATA_DIR})",
    )
    args = parser.parse_args()

    try:
        instrument_id = resolve_symbol(args.symbol)
    except SymbolNotFoundError:
        print(f"Error: symbol {args.symbol!r} not found in database.", file=sys.stderr)
        sys.exit(1)

    ticker = _get_ticker(instrument_id)
    kraken_pair = resolve_kraken_pair(instrument_id, ticker)
    file_path = Path(args.data_dir) / f"{kraken_pair}_60.csv"

    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Importing {file_path} → instrument_id={instrument_id!r} …")
    result = import_kraken_1h(instrument_id, file_path)
    print(
        f"Done: {result['rows_inserted']} rows upserted for {instrument_id}"
        f"  [{result['gap_closed_from']} → {result['gap_closed_to']}]"
    )
