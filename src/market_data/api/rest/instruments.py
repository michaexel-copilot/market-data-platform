"""REST instruments router."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from market_data.db.connection import get_connection
from market_data.ingestion.hyperliquid import get_hl_metadata_for_instruments
from market_data.models.api import (
    AmbiguousSymbolError,
    InstrumentListRequest,
    PaginatedResponse,
    SymbolNotFoundError,
)
from market_data.models.enums import AssetClass, Interval
from market_data.models.fundamentals import FundamentalsRecord
from market_data.models.instrument import InstrumentRecord

router = APIRouter(prefix="/v1/instruments", tags=["instruments"])

_VALID_TRADEABLE_ON = {"hyperliquid"}
_VALID_NETWORKS = {"mainnet", "testnet"}
_NATIVE_OHLCV_INTERVALS = ("1m", "5m", "1h", "1d")
_INTERVAL_ENUM_MAP = {
    "1m": Interval.ONE_MIN,
    "5m": Interval.FIVE_MIN,
    "1h": Interval.ONE_HOUR,
    "1d": Interval.ONE_DAY,
}
_AGGREGATION_SOURCE_PREFERENCE = {
    "5m": ("1m",),
    "1h": ("5m", "1m"),
    "1d": ("1h", "5m", "1m"),
}


class OhlcvAutoUpdateRequest(BaseModel):
    auto_update: bool


def _parse_instrument_row(row: tuple) -> dict:
    keys = [
        "instrument_id", "ticker", "full_name", "description", "asset_class",
        "exchange", "sector", "industry", "quote_currency", "launch_date",
        "is_active", "logo_url", "website_url", "first_seen_at", "last_updated_at",
    ]
    return dict(zip(keys, row))


def _validate_native_interval(interval: str) -> str:
    if interval not in _NATIVE_OHLCV_INTERVALS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported interval {interval!r}. Supported: {list(_NATIVE_OHLCV_INTERVALS)}",
        )
    return interval


def _load_ohlcv_update_settings(conn, instrument_id: str) -> dict[str, dict[str, bool]]:
    settings = {iv: {"auto_update": False} for iv in _NATIVE_OHLCV_INTERVALS}
    rows = conn.execute(
        "SELECT interval, auto_update FROM ohlcv_update_settings WHERE instrument_id = %s",
        [instrument_id],
    ).fetchall()
    for interval, auto_update in rows:
        if interval in settings:
            settings[interval] = {"auto_update": bool(auto_update)}
    return settings


def _bucket_start(ts: datetime, interval: str) -> datetime:
    ts = ts.astimezone(timezone.utc)
    if interval == "5m":
        return ts.replace(minute=(ts.minute // 5) * 5, second=0, microsecond=0)
    if interval == "1h":
        return ts.replace(minute=0, second=0, microsecond=0)
    if interval == "1d":
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    return ts.replace(second=0, microsecond=0)


def _aggregate_rows_to_interval(
    instrument_id: str,
    source_interval: str,
    target_interval: str,
    rows: list[tuple],
):
    from market_data.models.ohlcv import OHLCVRecord

    buckets: defaultdict[datetime, list[tuple]] = defaultdict(list)
    for row in rows:
        ts = row[0]
        buckets[_bucket_start(ts, target_interval)].append(row)

    records: list[OHLCVRecord] = []
    for bucket_ts, candles in sorted(buckets.items()):
        ordered = sorted(candles, key=lambda row: row[0])
        has_volume = any(row[5] is not None for row in ordered)
        volume_total = sum(float(row[5] or 0.0) for row in ordered)
        records.append(
            OHLCVRecord(
                instrument_id=instrument_id,
                interval=_INTERVAL_ENUM_MAP[target_interval],
                ts=bucket_ts,
                open=float(ordered[0][1]),
                high=max(float(row[2]) for row in ordered),
                low=min(float(row[3]) for row in ordered),
                close=float(ordered[-1][4]),
                volume=volume_total if has_volume else None,
                source=f"aggregated:{source_interval}",
                is_aggregated=True,
            )
        )
    return records


def _find_aggregation_source(conn, instrument_id: str, target_interval: str) -> tuple[str | None, datetime | None, datetime | None]:
    target_row = conn.execute(
        "SELECT MAX(ts) FROM ohlcv WHERE instrument_id = %s AND interval = %s",
        [instrument_id, target_interval],
    ).fetchone()
    target_last_ts = target_row[0] if target_row else None

    for candidate in _AGGREGATION_SOURCE_PREFERENCE[target_interval]:
        row = conn.execute(
            "SELECT MAX(ts) FROM ohlcv WHERE instrument_id = %s AND interval = %s",
            [instrument_id, candidate],
        ).fetchone()
        candidate_last_ts = row[0] if row else None
        if candidate_last_ts is None:
            continue
        if target_last_ts is None or candidate_last_ts > target_last_ts:
            return candidate, target_last_ts, candidate_last_ts

    return None, target_last_ts, None


@router.get("", response_model=PaginatedResponse)
async def list_instruments(
    asset_class: AssetClass | None = Query(default=None),
    is_active: bool = Query(default=True),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=5000),
    tradeable_on: str | None = Query(default=None),
    network: str = Query(default="mainnet"),
    sources: str | None = Query(default=None),
) -> PaginatedResponse:
    if tradeable_on is not None and tradeable_on not in _VALID_TRADEABLE_ON:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tradeable_on value {tradeable_on!r}. Valid values: {sorted(_VALID_TRADEABLE_ON)}",
        )
    if tradeable_on is not None and network not in _VALID_NETWORKS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid network value {network!r}. Valid values: {sorted(_VALID_NETWORKS)}",
        )

    source_list = [s.strip() for s in sources.split(",") if s.strip()] if sources else []

    conn = get_connection()

    if tradeable_on == "hyperliquid":
        # Join with instrument_hyperliquid to filter tradeable instruments
        base_table = (
            "instruments i "
            "JOIN instrument_hyperliquid h ON h.instrument_id = i.instrument_id "
            "  AND h.network = %s AND h.is_active = TRUE"
        )
        conditions = ["i.is_active = %s"]
        params: list = [network, is_active]
        if asset_class:
            conditions.append("i.asset_class = %s")
            params.append(str(asset_class))
        if q:
            conditions.append("(upper(i.ticker) LIKE upper(%s) OR upper(i.full_name) LIKE upper(%s))")
            pattern = f"%{q}%"
            params.extend([pattern, pattern])
        if source_list:
            conditions.append(
                "i.instrument_id IN ("
                "  SELECT instrument_id FROM instrument_source_intersection"
                "  WHERE source_short_name = ANY(%s)"
                "  GROUP BY instrument_id HAVING COUNT(DISTINCT source_short_name) = %s"
                ")"
            )
            params.extend([source_list, len(source_list)])

        where = " AND ".join(conditions)
        total_row = conn.execute(f"SELECT COUNT(*) FROM {base_table} WHERE {where}", params).fetchone()
        total = total_row[0] if total_row else 0

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT i.instrument_id, i.ticker, i.full_name, i.description, i.asset_class, i.exchange,
                   i.sector, i.industry, i.quote_currency, i.launch_date, i.is_active, i.logo_url,
                   i.website_url, i.first_seen_at, i.last_updated_at
            FROM {base_table} WHERE {where}
            ORDER BY i.ticker
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        ).fetchall()

        items = [_parse_instrument_row(r) for r in rows]

        # Embed HL metadata into each item
        if items:
            ids = [item["instrument_id"] for item in items]
            hl_meta = get_hl_metadata_for_instruments(conn, network, ids)
            for item in items:
                item["hyperliquid"] = hl_meta.get(item["instrument_id"])

    else:
        conditions = ["is_active = %s"]
        params = [is_active]
        if asset_class:
            conditions.append("asset_class = %s")
            params.append(str(asset_class))
        if q:
            conditions.append("(upper(ticker) LIKE upper(%s) OR upper(full_name) LIKE upper(%s))")
            pattern = f"%{q}%"
            params.extend([pattern, pattern])
        if source_list:
            conditions.append(
                "instrument_id IN ("
                "  SELECT instrument_id FROM instrument_source_intersection"
                "  WHERE source_short_name = ANY(%s)"
                "  GROUP BY instrument_id HAVING COUNT(DISTINCT source_short_name) = %s"
                ")"
            )
            params.extend([source_list, len(source_list)])

        where = " AND ".join(conditions)
        total_row = conn.execute(f"SELECT COUNT(*) FROM instruments WHERE {where}", params).fetchone()
        total = total_row[0] if total_row else 0

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT instrument_id, ticker, full_name, description, asset_class, exchange,
                   sector, industry, quote_currency, launch_date, is_active, logo_url,
                   website_url, first_seen_at, last_updated_at
            FROM instruments WHERE {where}
            ORDER BY ticker
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        ).fetchall()

        items = [_parse_instrument_row(r) for r in rows]

    next_page = page + 1 if offset + page_size < total else None
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items, next_page=next_page)


@router.get("/{symbol}", response_model=dict)
async def get_instrument(symbol: str) -> dict:
    from market_data.db.resolver import resolve_symbol
    instrument_id = resolve_symbol(symbol)
    conn = get_connection()
    row = conn.execute(
        """
        SELECT instrument_id, ticker, full_name, description, asset_class, exchange,
               sector, industry, quote_currency, launch_date, is_active, logo_url,
               website_url, first_seen_at, last_updated_at
        FROM instruments WHERE instrument_id = %s
        """,
        [instrument_id],
    ).fetchone()
    if not row:
        raise SymbolNotFoundError(symbol)
    return _parse_instrument_row(row)


@router.get("/{symbol}/fundamentals")
async def get_fundamentals(symbol: str) -> dict:
    from market_data.db.resolver import resolve_symbol
    instrument_id = resolve_symbol(symbol)
    conn = get_connection()
    base_row = conn.execute(
        "SELECT instrument_id, asset_class, launch_date FROM instruments WHERE instrument_id = %s",
        [instrument_id],
    ).fetchone()
    if not base_row:
        raise SymbolNotFoundError(symbol)
    asset_class = base_row[1]
    launch_date = base_row[2]

    result: dict = {"instrument_id": instrument_id, "asset_class": asset_class}
    if launch_date is not None:
        result["launch_date"] = launch_date.isoformat() if hasattr(launch_date, "isoformat") else str(launch_date)
    table_map = {
        "crypto":    "instrument_crypto",
        "equity":    "instrument_equity",
        "etf":       "instrument_etf",
        "fx":        "instrument_fx",
        "commodity": "instrument_commodity",
    }
    table = table_map.get(asset_class)
    if table:
        cur = conn.execute(
            f"SELECT * FROM {table} WHERE instrument_id = %s", [instrument_id]
        )
        row = cur.fetchone()
        if row:
            cols = [d.name for d in cur.description]
            result[asset_class] = dict(zip(cols, row))
    return result


@router.get("/{symbol}/ohlcv-availability")
async def get_ohlcv_availability(symbol: str) -> dict:
    """Return first/last timestamp per OHLCV interval for the given instrument.

    Native intervals (1m, 5m, 1h, 1d) are read from the ``ohlcv`` table.
    Derived intervals (1w, 4w, 1mth, 1y, 1ytd) are computed from views or
    daily data.  Intervals with no rows are omitted from the response.
    """
    from market_data.db.resolver import resolve_symbol

    instrument_id = resolve_symbol(symbol)
    conn = get_connection()

    # Verify instrument exists
    if not conn.execute(
        "SELECT 1 FROM instruments WHERE instrument_id = %s", [instrument_id]
    ).fetchone():
        raise SymbolNotFoundError(symbol)

    intervals: dict[str, dict] = {"1m": {"first": None, "last": None}}

    # ── Native intervals from ohlcv ──────────────────────────────────────
    rows = conn.execute(
        """
        SELECT interval,
               MIN(ts) AS first_ts,
               MAX(ts) AS last_ts
        FROM ohlcv
        WHERE instrument_id = %s
        GROUP BY interval
        """,
        [instrument_id],
    ).fetchall()
    for iv, first_ts, last_ts in rows:
        intervals[iv] = {"first": first_ts.isoformat() if first_ts else None,
                         "last":  last_ts.isoformat()  if last_ts  else None}

    # ── 1w — ohlcv_weekly view ───────────────────────────────────────────
    row = conn.execute(
        "SELECT MIN(ts), MAX(ts) FROM ohlcv_weekly WHERE instrument_id = %s",
        [instrument_id],
    ).fetchone()
    if row and row[0] is not None:
        intervals["1w"] = {"first": row[0].isoformat(), "last": row[1].isoformat()}

    # ── 4w — approximate: 4-week buckets aligned to epoch Monday ────────
    row = conn.execute(
        """
        SELECT MIN(week_bucket), MAX(week_bucket)
        FROM (
            SELECT DATE_TRUNC('week', ts) -
                   ((EXTRACT(DOW FROM DATE_TRUNC('week', ts))::INTEGER + 6) %% 7
                    %% 4) * INTERVAL '7 days' AS week_bucket
            FROM ohlcv
            WHERE instrument_id = %s AND interval = '1d'
        ) sub
        WHERE week_bucket IS NOT NULL
        """,
        [instrument_id],
    ).fetchone()
    if row and row[0] is not None:
        intervals["4w"] = {"first": str(row[0])[:10], "last": str(row[1])[:10]}

    # ── 1mth — ohlcv_monthly view ────────────────────────────────────────
    row = conn.execute(
        "SELECT MIN(ts), MAX(ts) FROM ohlcv_monthly WHERE instrument_id = %s",
        [instrument_id],
    ).fetchone()
    if row and row[0] is not None:
        intervals["1mth"] = {"first": row[0].isoformat(), "last": row[1].isoformat()}

    # ── 1y — group daily rows by calendar year ───────────────────────────
    row = conn.execute(
        """
        SELECT MIN(DATE_TRUNC('year', ts)), MAX(DATE_TRUNC('year', ts))
        FROM ohlcv
        WHERE instrument_id = %s AND interval = '1d'
        """,
        [instrument_id],
    ).fetchone()
    if row and row[0] is not None:
        intervals["1y"] = {"first": str(row[0])[:10], "last": str(row[1])[:10]}

    # ── 1ytd — daily rows since start of current year ───────────────────
    row = conn.execute(
        """
        SELECT MIN(ts), MAX(ts)
        FROM ohlcv
        WHERE instrument_id = %s AND interval = '1d'
          AND ts >= DATE_TRUNC('year', now())
        """,
        [instrument_id],
    ).fetchone()
    if row and row[0] is not None:
        intervals["1ytd"] = {"first": row[0].isoformat(), "last": row[1].isoformat()}

    return {"instrument_id": instrument_id, "intervals": intervals}


@router.get("/{symbol}/ohlcv-data-available")
async def get_ohlcv_data_available(symbol: str) -> dict:
    """Return the OHLCV data availability matrix for the given instrument.

    Returns a dict keyed by data source ``short_name``, each containing the
    four boolean interval flags ``has_1m``, ``has_5m``, ``has_1h``, ``has_1d``.
    """
    from market_data.db.resolver import resolve_symbol

    instrument_id = resolve_symbol(symbol)
    conn = get_connection()

    if not conn.execute(
        "SELECT 1 FROM instruments WHERE instrument_id = %s", [instrument_id]
    ).fetchone():
        raise SymbolNotFoundError(symbol)

    rows = conn.execute(
        """
        SELECT ds.short_name, oda.has_1m, oda.has_5m, oda.has_1h, oda.has_1d
        FROM ohlcv_data_available oda
        JOIN data_source ds ON ds.data_source_id = oda.data_source_id
        WHERE oda.instrument_id = %s
        ORDER BY ds.retrieval_priority NULLS LAST, ds.short_name
        """,
        [instrument_id],
    ).fetchall()

    sources: dict[str, dict] = {}
    for short_name, has_1m, has_5m, has_1h, has_1d in rows:
        sources[short_name] = {
            "has_1m": bool(has_1m),
            "has_5m": bool(has_5m),
            "has_1h": bool(has_1h),
            "has_1d": bool(has_1d),
        }

    return {"instrument_id": instrument_id, "sources": sources}


@router.get("/{symbol}/ohlcv-update-settings")
async def get_ohlcv_update_settings(symbol: str) -> dict:
    """Return persisted per-interval auto-update settings for an instrument."""
    from market_data.db.resolver import resolve_symbol

    instrument_id = resolve_symbol(symbol)
    conn = get_connection()
    if not conn.execute(
        "SELECT 1 FROM instruments WHERE instrument_id = %s",
        [instrument_id],
    ).fetchone():
        raise SymbolNotFoundError(symbol)

    return {
        "instrument_id": instrument_id,
        "intervals": _load_ohlcv_update_settings(conn, instrument_id),
    }


@router.put("/{symbol}/ohlcv-update-settings/{interval}")
async def put_ohlcv_update_setting(symbol: str, interval: str, req: OhlcvAutoUpdateRequest) -> dict:
    """Upsert the per-interval auto-update flag for an instrument."""
    from market_data.db.resolver import resolve_symbol

    interval = _validate_native_interval(interval)
    instrument_id = resolve_symbol(symbol)
    conn = get_connection()
    if not conn.execute(
        "SELECT 1 FROM instruments WHERE instrument_id = %s",
        [instrument_id],
    ).fetchone():
        raise SymbolNotFoundError(symbol)

    conn.execute(
        """
        INSERT INTO ohlcv_update_settings (instrument_id, interval, auto_update)
        VALUES (%s, %s, %s)
        ON CONFLICT (instrument_id, interval)
        DO UPDATE SET auto_update = excluded.auto_update
        """,
        [instrument_id, interval, req.auto_update],
    )
    return {
        "instrument_id": instrument_id,
        "interval": interval,
        "auto_update": req.auto_update,
    }


@router.post("/{symbol}/update-ohlcv/{interval}")
async def update_ohlcv_for_interval(symbol: str, interval: str) -> dict:
    """Update a single OHLCV interval for an instrument.

    - ``1m`` fetches fresh candles from Binance.
    - ``5m``/``1h``/``1d`` aggregate from the best available lower interval already
      stored in the database.
    """
    from market_data.connectors.binance import BinanceConnector
    from market_data.db.resolver import resolve_symbol
    from market_data.ingestion.writer import write_ohlcv

    interval = _validate_native_interval(interval)
    instrument_id = resolve_symbol(symbol)
    conn = get_connection()
    if not conn.execute(
        "SELECT 1 FROM instruments WHERE instrument_id = %s",
        [instrument_id],
    ).fetchone():
        raise SymbolNotFoundError(symbol)

    now = datetime.now(tz=timezone.utc)

    if interval == "1m":
        row = conn.execute(
            "SELECT MAX(ts) FROM ohlcv WHERE instrument_id = %s AND interval = '1m'",
            [instrument_id],
        ).fetchone()
        last_ts = row[0] if row else None
        since = (last_ts + timedelta(minutes=1)) if last_ts is not None else (now - timedelta(hours=24))
        if since >= now:
            since = now - timedelta(minutes=1)

        try:
            records = await BinanceConnector().fetch_ohlcv(
                instrument_id,
                Interval.ONE_MIN,
                since=since,
                until=now,
            )
            written = write_ohlcv(records)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"Binance 1m update failed: {exc}") from exc

        return {
            "instrument_id": instrument_id,
            "interval": interval,
            "source_interval": "binance",
            "written": written,
            "message": (
                f"Updated 1m OHLCV from Binance ({written} row(s) written)."
                if written > 0 else
                "No new 1m OHLCV rows were returned from Binance."
            ),
        }

    source_interval, target_last_ts, _source_last_ts = _find_aggregation_source(conn, instrument_id, interval)
    if source_interval is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"No newer lower-resolution OHLCV data is available to build {interval} candles for "
                f"{instrument_id!r}. Update 1m first and then retry."
            ),
        )

    params: list = [instrument_id, source_interval]
    query = (
        "SELECT ts, open, high, low, close, volume "
        "FROM ohlcv WHERE instrument_id = %s AND interval = %s"
    )
    if target_last_ts is not None:
        query += " AND ts >= %s"
        params.append(_bucket_start(target_last_ts, interval))
    query += " ORDER BY ts"

    rows = conn.execute(query, params).fetchall()
    records = _aggregate_rows_to_interval(instrument_id, source_interval, interval, rows)
    written = write_ohlcv(records)
    return {
        "instrument_id": instrument_id,
        "interval": interval,
        "source_interval": source_interval,
        "written": written,
        "message": (
            f"Updated {interval} OHLCV by aggregating newer {source_interval} data "
            f"({written} row(s) written)."
        ),
    }
