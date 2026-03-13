"""Admin REST router — management operations not part of the public API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from market_data.db.connection import get_connection
from market_data.db.migrate import migrate
from market_data.ingestion.import_ohlcv_cache import import_from_cache
from market_data.ingestion.migrate_fundamentals import migrate_fundamentals

router = APIRouter(prefix="/v1/admin", tags=["admin"])

# Intervals that have a corresponding has_<interval> column in ohlcv_data_available
_NATIVE_INTERVALS = {"1m", "5m", "1h", "1d"}


class ImportOhlcvCacheRequest(BaseModel):
    instrument_id: str
    interval: str


@router.post("/migrate-fundamentals")
async def run_migrate_fundamentals() -> dict:
    """Promote latest CoinMarketCap static data into canonical tables.

    Idempotent — safe to call multiple times.
    Returns ``{promoted, skipped, errors}``.
    """
    migrate()
    conn = get_connection()
    return migrate_fundamentals(conn)


@router.post("/import-ohlcv-cache")
async def run_import_ohlcv_cache(req: ImportOhlcvCacheRequest) -> dict:
    """Import OHLCV data for an instrument from the local ``/appdata`` cache.

    Resolves the best-fit data source from ``ohlcv_data_available``, checks the
    expected folder, parses matching files, and upserts into ``ohlcv``.

    Returns one of:
    - ``{status: "ok", rows_imported: N, files_processed: M}``
    - ``{status: "folder_not_found", expected_path: "...", source_short_name: "..."}``
    """
    interval = req.interval
    if interval not in _NATIVE_INTERVALS:
        raise HTTPException(
            status_code=422,
            detail=f"Interval {interval!r} is not a native interval; cache import supports: {sorted(_NATIVE_INTERVALS)}",
        )

    col = f"has_{interval.replace('m', 'm').replace('h', 'h').replace('d', 'd')}"
    # Map interval to the ohlcv_data_available column name
    col = f"has_{interval}"

    conn = get_connection()

    # Resolve best-fit source
    row = conn.execute(
        f"""
        SELECT ds.short_name
        FROM ohlcv_data_available oda
        JOIN data_source ds ON ds.data_source_id = oda.data_source_id
        WHERE oda.instrument_id = ?
          AND oda.{col} = TRUE
          AND ds.retrieval_priority IS NOT NULL
        ORDER BY ds.retrieval_priority ASC
        LIMIT 1
        """,
        [req.instrument_id],
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=422,
            detail=f"No data source covers interval {interval!r} for instrument {req.instrument_id!r}",
        )
    source_short_name = row[0]

    # Fetch ticker for file-matching
    ticker_row = conn.execute(
        "SELECT ticker FROM instruments WHERE instrument_id = ? LIMIT 1",
        [req.instrument_id],
    ).fetchone()
    ticker = ticker_row[0] if ticker_row else req.instrument_id

    result = import_from_cache(req.instrument_id, ticker, source_short_name, interval, conn)

    if result.get("status") == "folder_not_found":
        result["source_short_name"] = source_short_name

    return result
