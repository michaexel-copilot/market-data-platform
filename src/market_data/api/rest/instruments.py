"""REST instruments router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from market_data.db.connection import get_connection
from market_data.models.api import (
    AmbiguousSymbolError,
    InstrumentListRequest,
    PaginatedResponse,
    SymbolNotFoundError,
)
from market_data.models.enums import AssetClass
from market_data.models.fundamentals import FundamentalsRecord
from market_data.models.instrument import InstrumentRecord

router = APIRouter(prefix="/v1/instruments", tags=["instruments"])


def _parse_instrument_row(row: tuple) -> dict:
    keys = [
        "instrument_id", "ticker", "full_name", "description", "asset_class",
        "exchange", "sector", "industry", "quote_currency", "launch_date",
        "is_active", "logo_url", "website_url", "first_seen_at", "last_updated_at",
    ]
    return dict(zip(keys, row))


@router.get("", response_model=PaginatedResponse)
async def list_instruments(
    asset_class: AssetClass | None = Query(default=None),
    is_active: bool = Query(default=True),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=5000),
) -> PaginatedResponse:
    conn = get_connection()
    conditions = ["is_active = ?"]
    params: list = [is_active]
    if asset_class:
        conditions.append("asset_class = ?")
        params.append(str(asset_class))
    if q:
        conditions.append("(upper(ticker) LIKE upper(?) OR upper(full_name) LIKE upper(?))")
        pattern = f"%{q}%"
        params.extend([pattern, pattern])

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
        LIMIT ? OFFSET ?
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
        FROM instruments WHERE instrument_id = ?
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
        "SELECT instrument_id, asset_class FROM instruments WHERE instrument_id = ?",
        [instrument_id],
    ).fetchone()
    if not base_row:
        raise SymbolNotFoundError(symbol)
    asset_class = base_row[1]

    result: dict = {"instrument_id": instrument_id, "asset_class": asset_class}
    table_map = {
        "crypto":    "instrument_crypto",
        "equity":    "instrument_equity",
        "etf":       "instrument_etf",
        "fx":        "instrument_fx",
        "commodity": "instrument_commodity",
    }
    table = table_map.get(asset_class)
    if table:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE instrument_id = ?", [instrument_id]
        ).fetchone()
        if row:
            desc = conn.execute(f"DESCRIBE {table}").fetchall()
            cols = [d[0] for d in desc]
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
        "SELECT 1 FROM instruments WHERE instrument_id = ?", [instrument_id]
    ).fetchone():
        raise SymbolNotFoundError(symbol)

    intervals: dict[str, dict] = {}

    # ── Native intervals from ohlcv ──────────────────────────────────────
    rows = conn.execute(
        """
        SELECT interval,
               MIN(ts) AS first_ts,
               MAX(ts) AS last_ts
        FROM ohlcv
        WHERE instrument_id = ?
        GROUP BY interval
        """,
        [instrument_id],
    ).fetchall()
    for iv, first_ts, last_ts in rows:
        intervals[iv] = {"first": first_ts.isoformat() if first_ts else None,
                         "last":  last_ts.isoformat()  if last_ts  else None}

    # ── 1w — ohlcv_weekly view ───────────────────────────────────────────
    row = conn.execute(
        "SELECT MIN(ts), MAX(ts) FROM ohlcv_weekly WHERE instrument_id = ?",
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
                   ((EXTRACT(DOW FROM DATE_TRUNC('week', ts))::INTEGER + 6) % 7
                    % 4) * INTERVAL '7 days' AS week_bucket
            FROM ohlcv
            WHERE instrument_id = ? AND interval = '1d'
        ) sub
        WHERE week_bucket IS NOT NULL
        """,
        [instrument_id],
    ).fetchone()
    if row and row[0] is not None:
        intervals["4w"] = {"first": str(row[0])[:10], "last": str(row[1])[:10]}

    # ── 1mth — ohlcv_monthly view ────────────────────────────────────────
    row = conn.execute(
        "SELECT MIN(ts), MAX(ts) FROM ohlcv_monthly WHERE instrument_id = ?",
        [instrument_id],
    ).fetchone()
    if row and row[0] is not None:
        intervals["1mth"] = {"first": row[0].isoformat(), "last": row[1].isoformat()}

    # ── 1y — group daily rows by calendar year ───────────────────────────
    row = conn.execute(
        """
        SELECT MIN(DATE_TRUNC('year', ts)), MAX(DATE_TRUNC('year', ts))
        FROM ohlcv
        WHERE instrument_id = ? AND interval = '1d'
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
        WHERE instrument_id = ? AND interval = '1d'
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
        "SELECT 1 FROM instruments WHERE instrument_id = ?", [instrument_id]
    ).fetchone():
        raise SymbolNotFoundError(symbol)

    rows = conn.execute(
        """
        SELECT ds.short_name, oda.has_1m, oda.has_5m, oda.has_1h, oda.has_1d
        FROM ohlcv_data_available oda
        JOIN data_source ds ON ds.data_source_id = oda.data_source_id
        WHERE oda.instrument_id = ?
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
