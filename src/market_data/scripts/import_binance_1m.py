"""import-binance-1m — import Binance historical 1-minute OHLCV flat files into the platform.

The Binance klines CSV format is headerless with columns:
    open_time_ms, open, high, low, close, volume,
    close_time_ms, quote_asset_volume, number_of_trades,
    taker_buy_base_vol, taker_buy_quote_vol, ignore

open_time_ms is a Unix millisecond timestamp.

Usage:
    import-binance-1m --symbol BTC [--data-dir /mnt/ds420/data/binance/1-minute]

The Binance pair symbol is resolved as follows:
  1. Look up instrument_id in config/binance_pairs.yaml; if found, use the mapped value.
  2. Otherwise, construct {TICKER}USDT from instruments.ticker.
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

_BINANCE_SOURCE_ID = 6
_BATCH_SIZE = 5000
_DEFAULT_DATA_DIR = "/mnt/ds420/data/binance/1-minute"
_PAIRS_YAML = Path(__file__).parent.parent / "config" / "binance_pairs.yaml"


# ---------------------------------------------------------------------------
# Pair resolution
# ---------------------------------------------------------------------------

def _load_pair_overrides() -> dict[str, str]:
    if _PAIRS_YAML.exists():
        with _PAIRS_YAML.open() as fh:
            return yaml.safe_load(fh) or {}
    return {}


def resolve_binance_pair(instrument_id: str, ticker: str) -> str:
    """Return the Binance pair symbol for the given instrument.

    Checks config/binance_pairs.yaml for overrides; falls back to {TICKER}USDT.
    """
    overrides = _load_pair_overrides()
    if instrument_id in overrides:
        return overrides[instrument_id]
    return f"{ticker.upper()}USDT"


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
            INSERT INTO ohlcv_data_available
                (instrument_id, data_source_id, has_1m, has_5m, has_1h, has_1d)
            VALUES (%s, %s, TRUE, FALSE, FALSE, FALSE)
            ON CONFLICT (instrument_id, data_source_id) DO UPDATE SET
                has_1m = TRUE
            """,
            (instrument_id, _BINANCE_SOURCE_ID),
        )


# ---------------------------------------------------------------------------
# Core import
# ---------------------------------------------------------------------------

def _find_csv_files(binance_pair: str, data_dir: Path) -> list[Path]:
    """Return all matching CSV files for *binance_pair*, sorted chronologically."""
    pattern = f"{binance_pair}-1m-*.csv"
    files = sorted(data_dir.glob(pattern))
    return files


def import_binance_1m(instrument_id: str, binance_pair: str, data_dir: Path) -> dict:
    """Parse all CSV files for *binance_pair* and upsert 1m rows into ohlcv.

    Returns a dict with keys: files_processed, rows_inserted, earliest_ts, latest_ts.
    """
    csv_files = _find_csv_files(binance_pair, data_dir)
    if not csv_files:
        return {
            "files_processed": 0,
            "rows_inserted": 0,
            "earliest_ts": None,
            "latest_ts": None,
        }

    conn = get_connection()
    total_rows = 0
    earliest_ts: datetime | None = None
    latest_ts: datetime | None = None

    for csv_path in csv_files:
        rows: list[tuple] = []
        with csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            for row in reader:
                if len(row) < 6:
                    continue
                # Column 0: open_time in milliseconds
                open_time_ms = int(row[0])
                unix_ts = open_time_ms // 1000
                ts = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
                open_ = float(row[1])
                high = float(row[2])
                low = float(row[3])
                close = float(row[4])
                volume = float(row[5])
                trade_count = int(row[8]) if len(row) > 8 and row[8].strip() else None
                rows.append((
                    instrument_id,
                    ts,
                    open_,
                    high,
                    low,
                    close,
                    volume,
                    trade_count,
                    unix_ts // 60,  # tick_1m
                ))

        if not rows:
            continue

        file_earliest = rows[0][1]
        file_latest = rows[-1][1]
        if earliest_ts is None or file_earliest < earliest_ts:
            earliest_ts = file_earliest
        if latest_ts is None or file_latest > latest_ts:
            latest_ts = file_latest

        with conn.cursor() as cur:
            for i in range(0, len(rows), _BATCH_SIZE):
                batch = rows[i : i + _BATCH_SIZE]
                cur.executemany(
                    """
                    INSERT INTO ohlcv
                        (instrument_id, interval, ts, open, high, low, close,
                         volume, trade_count, source, ingested_at, is_aggregated, tick_1m)
                    VALUES (%s, '1m', %s, %s, %s, %s, %s, %s, %s, 'binance', NOW(), FALSE, %s)
                    ON CONFLICT (instrument_id, interval, ts) DO UPDATE SET
                        open        = excluded.open,
                        high        = excluded.high,
                        low         = excluded.low,
                        close       = excluded.close,
                        volume      = COALESCE(excluded.volume, ohlcv.volume),
                        trade_count = COALESCE(excluded.trade_count, ohlcv.trade_count),
                        source      = excluded.source,
                        ingested_at = excluded.ingested_at,
                        tick_1m     = excluded.tick_1m
                    """,
                    batch,
                )
                total_rows += len(batch)

        print(f"  {csv_path.name}: {len(rows)} rows")

    _upsert_data_available(conn, instrument_id)

    return {
        "files_processed": len(csv_files),
        "rows_inserted": total_rows,
        "earliest_ts": earliest_ts.isoformat() if earliest_ts else None,
        "latest_ts": latest_ts.isoformat() if latest_ts else None,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import Binance historical 1-minute OHLCV flat files into the platform."
    )
    parser.add_argument(
        "--symbol",
        required=True,
        help="HL/CMC ticker symbol (e.g. BTC)",
    )
    parser.add_argument(
        "--data-dir",
        default=_DEFAULT_DATA_DIR,
        help=f"Directory containing Binance *-1m-*.csv files (default: {_DEFAULT_DATA_DIR})",
    )
    args = parser.parse_args()

    try:
        instrument_id = resolve_symbol(args.symbol)
    except SymbolNotFoundError:
        print(f"Error: symbol {args.symbol!r} not found in database.", file=sys.stderr)
        sys.exit(1)

    ticker = _get_ticker(instrument_id)
    binance_pair = resolve_binance_pair(instrument_id, ticker)
    data_dir = Path(args.data_dir)

    if not data_dir.exists():
        print(f"Error: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    csv_files = _find_csv_files(binance_pair, data_dir)
    if not csv_files:
        print(
            f"Error: no files matching '{binance_pair}-1m-*.csv' found in {data_dir}",
            file=sys.stderr,
        )
        print(
            f"Hint: run 'download-binance-1m --symbol {args.symbol}' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"Importing {len(csv_files)} file(s) for {binance_pair} "
        f"→ instrument_id={instrument_id!r} …"
    )
    result = import_binance_1m(instrument_id, binance_pair, data_dir)
    print(
        f"\nDone: {result['rows_inserted']} rows upserted across "
        f"{result['files_processed']} file(s) for {instrument_id}"
        f"  [{result['earliest_ts']} → {result['latest_ts']}]"
    )
