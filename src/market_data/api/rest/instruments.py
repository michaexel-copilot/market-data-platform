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
