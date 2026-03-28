"""REST router — Kraken 1h historical import endpoints.

GET  /v1/instruments/{symbol}/kraken-1h-status   → gap status for the given symbol
POST /v1/instruments/{symbol}/import-kraken-1h   → trigger import from CSV file
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from market_data.db.connection import get_connection
from market_data.db.resolver import resolve_symbol
from market_data.models.api import SymbolNotFoundError
from market_data.scripts.import_kraken_1h import (
    _get_ticker,
    import_kraken_1h,
    resolve_kraken_pair,
)

router = APIRouter(prefix="/v1/instruments", tags=["kraken-import"])

_DATA_DIR = Path(os.getenv("KRAKEN_DATA_DIR", "/mnt/ds420/data/kraken/1-hour"))


def _resolve(symbol: str) -> tuple[str, str, str, Path]:
    """Resolve symbol → (instrument_id, ticker, kraken_pair, file_path)."""
    try:
        instrument_id = resolve_symbol(symbol.upper())
    except SymbolNotFoundError:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol!r} not found.")
    ticker = _get_ticker(instrument_id)
    kraken_pair = resolve_kraken_pair(instrument_id, ticker)
    file_path = _DATA_DIR / f"{kraken_pair}_60.csv"
    return instrument_id, ticker, kraken_pair, file_path


@router.get("/{symbol}/kraken-1h-status")
async def kraken_1h_status(symbol: str) -> dict:
    """Return Kraken 1h import status for the given symbol."""
    instrument_id, _ticker, kraken_pair, file_path = _resolve(symbol)

    has_file = file_path.exists()
    conn = get_connection()

    # Check if any Kraken rows already imported
    already_row = conn.execute(
        "SELECT EXISTS(SELECT 1 FROM ohlcv WHERE instrument_id = %s AND interval = '1h' AND source = 'kraken')",
        [instrument_id],
    ).fetchone()
    already_imported: bool = bool(already_row[0]) if already_row else False

    # Earliest non-Kraken 1h timestamp in DB
    earliest_row = conn.execute(
        """
        SELECT EXTRACT(EPOCH FROM MIN(ts))::BIGINT
        FROM ohlcv
        WHERE instrument_id = %s AND interval = '1h' AND source != 'kraken'
        """,
        [instrument_id],
    ).fetchone()
    earliest_db_unix: int | None = earliest_row[0] if earliest_row and earliest_row[0] else None
    earliest_db_ts: str | None = None
    if earliest_db_unix is not None:
        from datetime import datetime, timezone
        earliest_db_ts = datetime.fromtimestamp(earliest_db_unix, tz=timezone.utc).isoformat()

    # Launch date
    launch_row = conn.execute(
        "SELECT launch_date FROM instruments WHERE instrument_id = %s",
        [instrument_id],
    ).fetchone()
    launch_date: str | None = str(launch_row[0]) if launch_row and launch_row[0] else None

    # Count gap rows (CSV rows with ts < earliest_db_unix)
    gap_rows = 0
    if has_file and not already_imported:
        try:
            with file_path.open(encoding="utf-8") as fh:
                for line in fh:
                    first_col = line.split(",", 1)[0].strip()
                    if first_col.isdigit():
                        if earliest_db_unix is None or int(first_col) < earliest_db_unix:
                            gap_rows += 1
        except OSError:
            gap_rows = 0

    return {
        "instrument_id": instrument_id,
        "kraken_pair": kraken_pair,
        "has_file": has_file,
        "launch_date": launch_date,
        "earliest_db_ts": earliest_db_ts,
        "gap_rows": gap_rows,
        "already_imported": already_imported,
    }


@router.post("/{symbol}/import-kraken-1h")
async def import_kraken_1h_endpoint(symbol: str) -> dict:
    """Trigger import of Kraken 1h CSV for the given symbol."""
    instrument_id, _ticker, kraken_pair, file_path = _resolve(symbol)

    if not file_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"No Kraken CSV found for {symbol!r}. Expected: {file_path}",
        )

    result = import_kraken_1h(instrument_id, file_path)
    return {"instrument_id": instrument_id, **result}
