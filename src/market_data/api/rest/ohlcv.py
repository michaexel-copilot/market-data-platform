"""REST OHLCV router."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from market_data.db.connection import get_connection
from market_data.models.api import PaginatedResponse, SymbolNotFoundError
from market_data.models.enums import AssetClass, Interval

router = APIRouter(prefix="/v1/ohlcv", tags=["ohlcv"])


@router.get("/{symbol}", response_model=PaginatedResponse)
async def get_ohlcv(
    symbol: str,
    interval: Interval = Query(default=Interval.ONE_DAY),
    since: str | None = Query(default=None, description="ISO 8601 UTC datetime"),
    until: str | None = Query(default=None, description="ISO 8601 UTC datetime"),
    asset_class: AssetClass | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=1000, ge=1, le=5000),
) -> PaginatedResponse:
    from market_data.db.resolver import resolve_symbol
    instrument_id = resolve_symbol(symbol, asset_class)

    since_dt: datetime | None = None
    until_dt: datetime | None = None
    if since:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    if until:
        until_dt = datetime.fromisoformat(until.replace("Z", "+00:00"))

    conn = get_connection()
    conditions = ["instrument_id = %s", "interval = %s"]
    params: list = [instrument_id, str(interval)]
    if since_dt:
        conditions.append("ts >= %s")
        params.append(since_dt)
    if until_dt:
        conditions.append("ts <= %s")
        params.append(until_dt)

    where = " AND ".join(conditions)
    total_row = conn.execute(f"SELECT COUNT(*) FROM ohlcv WHERE {where}", params).fetchone()
    total = total_row[0] if total_row else 0

    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""
        SELECT instrument_id, interval, ts, open, high, low, close,
               volume, vwap, trade_count, market_cap, source, ingested_at
        FROM ohlcv
        WHERE {where}
        ORDER BY ts ASC
        LIMIT %s OFFSET %s
        """,
        params + [page_size, offset],
    ).fetchall()

    cols = [
        "instrument_id", "interval", "ts", "open", "high", "low", "close",
        "volume", "vwap", "trade_count", "market_cap", "source", "ingested_at",
    ]
    items = [dict(zip(cols, row)) for row in rows]
    next_page = page + 1 if offset + page_size < total else None
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items, next_page=next_page)
