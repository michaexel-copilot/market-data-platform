"""import-cryptodatadownload-1h — import cryptodatadownload.com hourly OHLCV
flat files into the platform.

The CryptoDataDownload CSV format has an optional title line followed by a
header row:
    https://www.CryptoDataDownload.com
    Unix,Date,Symbol,Open,High,Low,Close,Volume {BASE},Volume {QUOTE},tradecount

Unix is a millisecond timestamp; rows may be in descending (newest-first) order,
so columns are read positionally rather than assuming a particular sort order.

Usage:
    import-cryptodatadownload-1h --symbol BTC [--exchange Binance]
                                  [--data-dir /mnt/ds420/data/cryptodatadownload/1-hour]
    import-cryptodatadownload-1h --all
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data.db.connection import get_connection
from market_data.db.resolver import resolve_symbol
from market_data.models.api import SymbolNotFoundError
from market_data.scripts.download_cryptodatadownload_1h import (
    _active_crypto_instruments,
    _get_ticker,
    resolve_cdd_pair,
)

_CDD_SOURCE_ID = 7
_BATCH_SIZE = 5000
_DEFAULT_DATA_DIR = "/mnt/ds420/data/cryptodatadownload/1-hour"
_DEFAULT_EXCHANGE = "Binance"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _upsert_data_available(conn: Any, instrument_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ohlcv_data_available
                (instrument_id, data_source_id, has_1m, has_5m, has_1h, has_1d)
            VALUES (%s, %s, FALSE, FALSE, TRUE, FALSE)
            ON CONFLICT (instrument_id, data_source_id) DO UPDATE SET
                has_1h = TRUE
            """,
            (instrument_id, _CDD_SOURCE_ID),
        )


# ---------------------------------------------------------------------------
# Core import
# ---------------------------------------------------------------------------

def _parse_rows(file_path: Path) -> list[list[str]]:
    """Return the data rows of a CDD CSV, skipping the title line (if present) and header."""
    with file_path.open(newline="", encoding="utf-8") as fh:
        lines = fh.readlines()
    if lines and not lines[0].strip().lower().startswith("unix"):
        lines = lines[1:]  # drop "https://www.CryptoDataDownload.com" title line
    reader = csv.reader(lines)
    next(reader, None)  # drop header row
    return list(reader)


def import_cryptodatadownload_1h(instrument_id: str, file_path: Path) -> dict:
    """Parse CSV and upsert 1h rows into ohlcv.

    Returns a dict with keys: rows_inserted, earliest_ts, latest_ts.
    """
    rows: list[tuple] = []
    for row in _parse_rows(file_path):
        if len(row) < 7:
            continue
        try:
            unix_ts = int(row[0]) // 1000  # column is milliseconds
            ts = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
            open_ = float(row[3])
            high = float(row[4])
            low = float(row[5])
            close = float(row[6])
            volume = float(row[7]) if len(row) > 7 and row[7].strip() else None
            trade_count = int(row[9]) if len(row) > 9 and row[9].strip() else None
        except (ValueError, IndexError):
            continue
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
        return {"rows_inserted": 0, "earliest_ts": None, "latest_ts": None}

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
                VALUES
                    (%s, '1h', %s, %s, %s, %s, %s, %s, %s, 'cryptodatadownload', NOW(), FALSE, %s)
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

    timestamps = [r[1] for r in rows]
    return {
        "rows_inserted": total,
        "earliest_ts": min(timestamps).isoformat(),
        "latest_ts": max(timestamps).isoformat(),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _import_one(instrument_id: str, ticker: str, exchange: str, data_dir: Path) -> bool:
    pair = resolve_cdd_pair(instrument_id, ticker)
    file_path = data_dir / f"{exchange}_{pair}_1h.csv"
    if not file_path.exists():
        print(f"  skip  {instrument_id} — no file: {file_path}", file=sys.stderr)
        return False
    result = import_cryptodatadownload_1h(instrument_id, file_path)
    print(
        f"  {instrument_id}: {result['rows_inserted']} rows upserted"
        f"  [{result['earliest_ts']} → {result['latest_ts']}]"
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import cryptodatadownload.com hourly OHLCV flat files into the platform."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--symbol",
        help="HL/CMC ticker symbol (e.g. BTC)",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Import for every active crypto instrument in the database",
    )
    parser.add_argument(
        "--exchange",
        default=_DEFAULT_EXCHANGE,
        help=f"Exchange listing used to name downloaded files (default: {_DEFAULT_EXCHANGE})",
    )
    parser.add_argument(
        "--data-dir",
        default=_DEFAULT_DATA_DIR,
        help=(
            "Directory containing {Exchange}_{PAIR}_1h.csv files "
            f"(default: {_DEFAULT_DATA_DIR})"
        ),
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Error: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    if args.all:
        instruments = _active_crypto_instruments()
        if not instruments:
            print("No active crypto instruments found.", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            instrument_id = resolve_symbol(args.symbol)
        except SymbolNotFoundError:
            print(f"Error: symbol {args.symbol!r} not found in database.", file=sys.stderr)
            sys.exit(1)
        instruments = [(instrument_id, _get_ticker(instrument_id))]

    print(f"Importing {len(instruments)} instrument(s) from {data_dir} …")
    imported = 0
    for instrument_id, ticker in instruments:
        if _import_one(instrument_id, ticker, args.exchange, data_dir):
            imported += 1

    print(f"\nDone: {imported}/{len(instruments)} instrument(s) imported.")
    if imported == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
