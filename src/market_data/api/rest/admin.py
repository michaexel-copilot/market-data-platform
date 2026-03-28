"""Admin REST router — management operations not part of the public API."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from market_data.db.connection import get_connection
from market_data.db.migrate import migrate
from market_data.ingestion.hyperliquid import upsert_hl_pairs
from market_data.ingestion.import_ohlcv_cache import import_from_cache
from market_data.ingestion.migrate_fundamentals import migrate_fundamentals

router = APIRouter(prefix="/v1/admin", tags=["admin"])

# Intervals that have a corresponding has_<interval> column in ohlcv_data_available
_NATIVE_INTERVALS = {"1m", "5m", "1h", "1d"}
_VALID_HL_NETWORKS = {"mainnet", "testnet"}


class ImportOhlcvCacheRequest(BaseModel):
    instrument_id: str
    interval: str


class ComputeIndicatorsRequest(BaseModel):
    strategy: str
    symbol: str | None = None
    sl_short: float = 10.0
    sl_long: float = 10.0
    pos_usd: float = 100.0


class ComputeIndicatorsV2Request(BaseModel):
    symbol: str | None = None
    sl_short: float = 10.0
    sl_long: float = 10.0
    tp_pct: float = 5.0
    pos_usd: float = 100.0


class ImportOhlcvRequest(BaseModel):
    interval: str
    symbol: str | None = None


class ImportCmcStaticRequest(BaseModel):
    dir: str | None = None


class ImportHLPairsRequest(BaseModel):
    network: str = "mainnet"


class RunIngestRequest(BaseModel):
    interval: str
    connector: str | None = None
    symbol: str | None = None
    asset_class: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    fill_gaps: bool = True


class SmartUpdateOhlcvRequest(BaseModel):
    instrument_id: str


def _aggregate_1m_to_1h(instrument_id: str, records_1m: list) -> list:
    """Aggregate 1-minute OHLCV records into synthetic 1-hour candles.

    Each output candle is marked ``is_aggregated = True`` with
    ``source = 'aggregated:binance_1m'``.
    """
    from collections import defaultdict

    from market_data.models.enums import Interval
    from market_data.models.ohlcv import OHLCVRecord

    buckets: defaultdict = defaultdict(list)
    for r in records_1m:
        hour_ts = r.ts.replace(minute=0, second=0, microsecond=0, tzinfo=r.ts.tzinfo)
        buckets[hour_ts].append(r)

    aggregated: list = []
    for hour_ts, candles in sorted(buckets.items()):
        candles_sorted = sorted(candles, key=lambda c: c.ts)
        vol = sum(c.volume for c in candles_sorted if c.volume is not None)
        aggregated.append(
            OHLCVRecord(
                instrument_id=instrument_id,
                interval=Interval.ONE_HOUR,
                ts=hour_ts,
                open=candles_sorted[0].open,
                high=max(c.high for c in candles_sorted),
                low=min(c.low for c in candles_sorted),
                close=candles_sorted[-1].close,
                volume=vol if vol else None,
                source="aggregated:binance_1m",
                is_aggregated=True,
            )
        )
    return aggregated


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
    elif result.get("status") == "error":
        details = result.get("errors") or [result.get("message", "Unknown import error")]
        raise HTTPException(status_code=500, detail="; ".join(str(d) for d in details))

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


@router.post("/compute-indicators-v2")
def run_compute_indicators_v2(req: ComputeIndicatorsV2Request) -> dict:
    """Compute best_sma_exit_v1 indicators for one or all active instruments."""
    from market_data.strategies.registry import STRATEGY_REGISTRY

    strategy_name = "best_sma_exit_v1"
    strategy_fn = STRATEGY_REGISTRY[strategy_name]
    parameters = {
        "sl_short": req.sl_short,
        "sl_long": req.sl_long,
        "tp_pct": req.tp_pct,
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
                    [instrument_id, strategy_name, indicator_name, float(indicator_value), params_json],
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


@router.post("/import-hl-pairs")
async def run_import_hl_pairs(req: ImportHLPairsRequest) -> dict:
    """Fetch Hyperliquid perpetual pairs and upsert into instrument_hyperliquid.

    Returns ``{upserted, unmatched, deactivated}``.
    """
    if req.network not in _VALID_HL_NETWORKS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid network {req.network!r}. Valid values: {sorted(_VALID_HL_NETWORKS)}",
        )

    from market_data.connectors.hyperliquid import HyperliquidConnector, reconcile_hl_pairs

    connector = HyperliquidConnector()
    pairs = await connector.fetch_hl_pairs(req.network)
    conn = get_connection()
    reconciled = reconcile_hl_pairs(pairs, conn)
    unmatched = len(pairs) - len(reconciled)
    upserted, deactivated = upsert_hl_pairs(conn, req.network, reconciled)
    return {"upserted": upserted, "unmatched": unmatched, "deactivated": deactivated}


@router.post("/run-ingest")
async def run_ingest(req: RunIngestRequest) -> dict:
    """Manually trigger an ingestion job for a specific interval.

    Optional filters: ``connector`` (data source name), ``symbol`` (single ticker),
    and ``since``/``until`` (UTC datetime window). If omitted the default lookback
    heuristic is used and all active instruments are processed.

    Returns ``{written, errors, skipped, interval, connector, symbol}``.
    """
    if req.interval not in _NATIVE_INTERVALS:
        raise HTTPException(
            status_code=422,
            detail=f"Interval {req.interval!r} is not supported. Supported: {sorted(_NATIVE_INTERVALS)}",
        )

    from market_data.models.enums import AssetClass, Interval
    from market_data.ingestion.jobs import _run_interval_job

    asset_class_enum: AssetClass | None = None
    if req.asset_class:
        try:
            asset_class_enum = AssetClass(req.asset_class.lower())
        except ValueError:
            valid = [e.value for e in AssetClass]
            raise HTTPException(
                status_code=422,
                detail=f"Unknown asset_class {req.asset_class!r}. Valid values: {valid}",
            ) from None

    _INTERVAL_MAP: dict[str, Interval] = {
        "1m": Interval.ONE_MIN,
        "5m": Interval.FIVE_MIN,
        "1h": Interval.ONE_HOUR,
        "1d": Interval.ONE_DAY,
    }
    interval_enum = _INTERVAL_MAP[req.interval]

    instrument_id: str | None = None
    if req.symbol:
        from market_data.db.resolver import resolve_symbol
        from market_data.models.api import AmbiguousSymbolError, SymbolNotFoundError
        try:
            instrument_id = resolve_symbol(req.symbol, asset_class=asset_class_enum)
        except AmbiguousSymbolError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"{exc}. Pass asset_class to disambiguate.",
            ) from exc
        except SymbolNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        stats = await _run_interval_job(
            interval_enum,
            connector_name=req.connector,
            instrument_id=instrument_id,
            asset_class=asset_class_enum,
            since=req.since,
            until=req.until,
            fill_gaps=req.fill_gaps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        **stats,
        "interval": req.interval,
        "connector": req.connector,
        "symbol": req.symbol,
        "asset_class": req.asset_class,
    }


@router.post("/smart-update-ohlcv")
async def run_smart_update_ohlcv(req: SmartUpdateOhlcvRequest) -> dict:
    """Smart OHLCV update for a single instrument.

    Performs the following steps automatically:

    1. **1h freshness check** — if the most recent 1h candle is older than 5 hours
       (or no 1h data exists), trigger the ``ohlcv_1h`` ingestion job for this instrument.
    2. **1m gap fill via Binance** — if the instrument has Binance 1m coverage
       (per ``ohlcv_data_available``), fetch 1m candles for the gap between the most recent
       1m candle and now, then aggregate them into synthetic 1h candles
       (``is_aggregated = TRUE``).  Aggregated candles are stored with
       ``source = 'aggregated:binance_1m'`` and will be overwritten automatically when
       real primary-source 1h data arrives later.

    Returns a ``steps`` list with the outcome of each stage and a ``total_written``
    summary count.
    """
    from datetime import timedelta

    from market_data.models.enums import Interval
    from market_data.ingestion.jobs import _run_interval_job
    from market_data.ingestion.writer import write_ohlcv

    _STALE_THRESHOLD_HOURS = 5

    conn = get_connection()
    steps: list[dict] = []
    total_written = 0
    now = datetime.now(tz=timezone.utc)

    # ── Validate instrument exists ────────────────────────────────────────────
    inst_row = conn.execute(
        "SELECT ticker, asset_class FROM instruments WHERE instrument_id = %s LIMIT 1",
        [req.instrument_id],
    ).fetchone()
    if inst_row is None:
        raise HTTPException(status_code=404, detail=f"Instrument {req.instrument_id!r} not found")
    ticker, asset_class_str = inst_row[0], inst_row[1]

    # ── Step 1: 1h freshness check ────────────────────────────────────────────
    row_1h = conn.execute(
        "SELECT MAX(ts) FROM ohlcv WHERE instrument_id = %s AND interval = '1h'",
        [req.instrument_id],
    ).fetchone()
    last_1h_ts: datetime | None = row_1h[0] if row_1h else None

    is_stale = (
        last_1h_ts is None
        or (now - last_1h_ts).total_seconds() > _STALE_THRESHOLD_HOURS * 3600
    )
    steps.append({
        "step": "1h_freshness_check",
        "status": "stale" if is_stale else "fresh",
        "last_ts": last_1h_ts.isoformat() if last_1h_ts else None,
        "threshold_hours": _STALE_THRESHOLD_HOURS,
    })

    # ── Step 2: 1h ingest (only if stale) ────────────────────────────────────
    ingest_written = 0
    if is_stale:
        try:
            stats = await _run_interval_job(
                Interval.ONE_HOUR,
                instrument_id=req.instrument_id,
                fill_gaps=True,
            )
            ingest_written = stats.get("written", 0)
            total_written += ingest_written
            steps.append({"step": "1h_ingest", "status": "ok", "written": ingest_written})
        except Exception as exc:  # noqa: BLE001
            steps.append({"step": "1h_ingest", "status": "error", "error": str(exc)})
    else:
        steps.append({"step": "1h_ingest", "status": "skipped", "written": 0})

    # ── Step 3: 1m gap check ──────────────────────────────────────────────────
    row_1m = conn.execute(
        "SELECT MAX(ts) FROM ohlcv WHERE instrument_id = %s AND interval = '1m'",
        [req.instrument_id],
    ).fetchone()
    last_1m_ts: datetime | None = row_1m[0] if row_1m else None

    gap_start = last_1m_ts or (now - timedelta(hours=_STALE_THRESHOLD_HOURS))
    gap_hours = (now - gap_start).total_seconds() / 3600

    has_gap = gap_hours > 0.1  # at least ~6 minutes
    steps.append({
        "step": "1m_gap_check",
        "status": "gap" if has_gap else "no_gap",
        "gap_start": gap_start.isoformat(),
        "gap_hours": round(gap_hours, 2),
    })

    # ── Step 4: Check Binance 1m availability ────────────────────────────────
    binance_row = conn.execute(
        """
        SELECT 1
        FROM ohlcv_data_available oda
        JOIN data_source ds ON ds.data_source_id = oda.data_source_id
        WHERE oda.instrument_id = %s
          AND oda.has_1m = TRUE
          AND ds.short_name = 'binance'
        LIMIT 1
        """,
        [req.instrument_id],
    ).fetchone()
    binance_available = binance_row is not None
    steps.append({
        "step": "binance_availability",
        "status": "available" if binance_available else "unavailable",
    })

    # ── Steps 5–6: Fetch 1m + aggregate to 1h ────────────────────────────────
    if has_gap and binance_available:
        from market_data.connectors.binance import BinanceConnector

        connector = BinanceConnector()
        try:
            records_1m = await connector.fetch_ohlcv(
                req.instrument_id,
                Interval.ONE_MIN,
                since=gap_start,
                until=now,
            )
            steps.append({"step": "1m_fetch", "status": "ok", "fetched": len(records_1m)})
        except Exception as exc:  # noqa: BLE001
            steps.append({"step": "1m_fetch", "status": "error", "error": str(exc)})
            records_1m = []

        if records_1m:
            aggregated = _aggregate_1m_to_1h(req.instrument_id, records_1m)
            agg_written = write_ohlcv(aggregated)
            total_written += agg_written
            steps.append({"step": "1h_aggregation", "status": "ok", "written": agg_written})
        else:
            steps.append({"step": "1h_aggregation", "status": "skipped", "written": 0})
    else:
        reason = "no_gap" if not has_gap else "binance_unavailable"
        steps.append({"step": "1m_fetch",      "status": "skipped", "reason": reason})
        steps.append({"step": "1h_aggregation","status": "skipped", "reason": reason})

    return {"steps": steps, "total_written": total_written}


# ── Scheduler job admin ────────────────────────────────────────────────────────

@router.get("/scheduler/jobs")
def list_scheduler_jobs() -> list[dict]:
    """Return the enabled state of every known scheduler job."""
    from market_data.db.scheduler_jobs import load_job_states

    conn = get_connection()
    states = load_job_states(conn)
    return [{"job_id": job_id, "enabled": enabled} for job_id, enabled in sorted(states.items())]


@router.post("/scheduler/jobs/{job_id}/enable")
async def enable_scheduler_job(job_id: str) -> dict:
    """Enable a scheduler job and, if the scheduler is running, resume it immediately."""
    from market_data.db.scheduler_jobs import set_job_enabled
    from market_data.ingestion.scheduler import _JOB_REGISTRY, get_scheduler

    conn = get_connection()
    try:
        set_job_enabled(conn, job_id, enabled=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    scheduler = get_scheduler()
    if scheduler is not None:
        existing = scheduler.get_job(job_id)
        if existing is not None:
            existing.resume()
        else:
            # Job was disabled at start-up and never added — add it now.
            if job_id in _JOB_REGISTRY:
                func, trigger_factory = _JOB_REGISTRY[job_id]
                scheduler.add_job(
                    func,
                    trigger=trigger_factory(),
                    id=job_id,
                    max_instances=1,
                    coalesce=True,
                )

    return {"job_id": job_id, "enabled": True}


@router.post("/scheduler/jobs/{job_id}/disable")
async def disable_scheduler_job(job_id: str) -> dict:
    """Disable a scheduler job and, if the scheduler is running, pause it immediately."""
    from market_data.db.scheduler_jobs import set_job_enabled
    from market_data.ingestion.scheduler import get_scheduler

    conn = get_connection()
    try:
        set_job_enabled(conn, job_id, enabled=False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    scheduler = get_scheduler()
    if scheduler is not None:
        job = scheduler.get_job(job_id)
        if job is not None:
            job.pause()

    return {"job_id": job_id, "enabled": False}
