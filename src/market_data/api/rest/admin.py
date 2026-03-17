"""Admin REST router — management operations not part of the public API."""
from __future__ import annotations

import os
import time
from pathlib import Path

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


class ComputeIndicatorsRequest(BaseModel):
    strategy: str
    symbol: str | None = None
    sl_short: float = 10.0
    sl_long: float = 10.0
    pos_usd: float = 100.0


class ImportOhlcvRequest(BaseModel):
    interval: str
    symbol: str | None = None


class ImportCmcStaticRequest(BaseModel):
    dir: str | None = None


@router.post("/import-ohlcv")
def run_import_ohlcv(req: ImportOhlcvRequest) -> dict:
    """Bulk-import OHLCV data from the local eodhd cache for active instruments.

    Dispatched to the thread pool (plain def) so long-running bulk runs do not
    block the event loop.

    Returns ``{ok, errors, results}``.
    """
    if req.interval not in _NATIVE_INTERVALS:
        raise HTTPException(
            status_code=422,
            detail=f"Interval {req.interval!r} is not supported. Supported: {sorted(_NATIVE_INTERVALS)}",
        )

    conn = get_connection()

    if req.symbol:
        from market_data.db.resolver import resolve_symbol
        from market_data.models.api import SymbolNotFoundError
        try:
            instrument_id = resolve_symbol(req.symbol)
        except SymbolNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        ticker_row = conn.execute(
            "SELECT ticker FROM instruments WHERE instrument_id = %s LIMIT 1",
            [instrument_id],
        ).fetchone()
        rows = [(instrument_id, ticker_row[0] if ticker_row else req.symbol)]
    else:
        rows = conn.execute(
            "SELECT instrument_id, ticker FROM instruments WHERE is_active = TRUE ORDER BY ticker"
        ).fetchall()

    ok_count = 0
    err_count = 0
    results = []

    for instrument_id, ticker in rows:
        t0 = time.monotonic()
        try:
            result = import_from_cache(instrument_id, ticker, "eodhd", req.interval, conn)
            elapsed = time.monotonic() - t0
            status = result.get("status", "ok")
            if status == "ok":
                ok_count += 1
                results.append({
                    "ticker": ticker,
                    "status": "ok",
                    "rows_imported": result.get("rows_imported", 0),
                    "elapsed_s": round(elapsed, 3),
                })
            else:
                err_count += 1
                results.append({
                    "ticker": ticker,
                    "status": status,
                    "error": result.get("expected_path", str(result)),
                    "elapsed_s": round(elapsed, 3),
                })
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - t0
            err_count += 1
            results.append({"ticker": ticker, "status": "error", "error": str(exc), "elapsed_s": round(elapsed, 3)})

    return {"ok": ok_count, "errors": err_count, "results": results}


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
        WHERE oda.instrument_id = %s
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
        "SELECT ticker FROM instruments WHERE instrument_id = %s LIMIT 1",
        [req.instrument_id],
    ).fetchone()
    ticker = ticker_row[0] if ticker_row else req.instrument_id

    result = import_from_cache(req.instrument_id, ticker, source_short_name, interval, conn)

    if result.get("status") == "folder_not_found":
        result["source_short_name"] = source_short_name

    return result


@router.post("/compute-indicators")
def run_compute_indicators(req: ComputeIndicatorsRequest) -> dict:
    """Compute strategy indicators for one or all active instruments.

    Dispatched to the thread pool (plain def) so long-running bulk runs do not
    block the event loop.

    Returns ``{ok, errors, results}``.
    """
    from market_data.strategies.registry import STRATEGY_REGISTRY

    if req.strategy not in STRATEGY_REGISTRY:
        available = ", ".join(sorted(STRATEGY_REGISTRY))
        raise HTTPException(
            status_code=422,
            detail=f"Unknown strategy {req.strategy!r}. Available: {available}",
        )

    strategy_fn = STRATEGY_REGISTRY[req.strategy]
    parameters = {
        "sl_short": req.sl_short,
        "sl_long": req.sl_long,
        "pos_usd": req.pos_usd,
    }

    conn = get_connection()

    if req.symbol:
        from market_data.db.resolver import resolve_symbol
        from market_data.models.api import SymbolNotFoundError
        try:
            instrument_id = resolve_symbol(req.symbol)
        except SymbolNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        ticker_row = conn.execute(
            "SELECT ticker FROM instruments WHERE instrument_id = %s LIMIT 1",
            [instrument_id],
        ).fetchone()
        rows = [(instrument_id, ticker_row[0] if ticker_row else req.symbol)]
    else:
        rows = conn.execute(
            "SELECT instrument_id, ticker FROM instruments WHERE is_active = TRUE ORDER BY ticker"
        ).fetchall()

    import json as _json

    ok_count = 0
    err_count = 0
    results = []

    for instrument_id, ticker in rows:
        t0 = time.monotonic()
        try:
            indicators = strategy_fn(instrument_id, parameters)
            params_json = _json.dumps(parameters)
            for indicator_name, indicator_value in indicators.items():
                conn.execute(
                    """
                    INSERT INTO trading_strategies
                        (instrument_id, strategy_name, indicator_name, indicator_value, parameters, computed_at)
                    VALUES (%s, %s, %s, %s, %s, now())
                    ON CONFLICT (instrument_id, strategy_name, indicator_name)
                    DO UPDATE SET
                        indicator_value = excluded.indicator_value,
                        parameters      = excluded.parameters,
                        computed_at     = excluded.computed_at
                    """,
                    [instrument_id, req.strategy, indicator_name, float(indicator_value), params_json],
                )
            elapsed = time.monotonic() - t0
            ok_count += 1
            results.append({"ticker": ticker, "status": "ok", "elapsed_s": round(elapsed, 3)})
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - t0
            err_count += 1
            results.append({"ticker": ticker, "status": "error", "error": str(exc), "elapsed_s": round(elapsed, 3)})

    return {"ok": ok_count, "errors": err_count, "results": results}


@router.post("/import-cmc-static")
def run_import_cmc_static(req: ImportCmcStaticRequest) -> dict:
    """Import CoinMarketCap static TSV snapshots from the server filesystem.

    The directory is resolved in order: request body ``dir`` field →
    ``CMC_STATIC_DIR`` environment variable → HTTP 422 error.

    Dispatched to the thread pool (plain def) to avoid blocking the event loop.
    """
    from market_data.ingestion.import_coinmarketcap_static import run_import

    raw_dir = req.dir or os.getenv("CMC_STATIC_DIR", "")
    if not raw_dir:
        raise HTTPException(
            status_code=422,
            detail="No directory specified and CMC_STATIC_DIR is not set",
        )

    directory = Path(raw_dir)
    if not directory.exists():
        raise HTTPException(
            status_code=422,
            detail=f"Directory does not exist: {directory}",
        )
    if not directory.is_dir():
        raise HTTPException(
            status_code=422,
            detail=f"Path is not a directory: {directory}",
        )

    counts = run_import(directory)
    return counts if counts else {}
