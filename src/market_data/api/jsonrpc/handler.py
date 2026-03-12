"""JSON-RPC 2.0 handler.

Mounted at POST /jsonrpc on the FastAPI app.
Supports single and batch (list) requests per the JSON-RPC 2.0 spec.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from market_data.models.api import AmbiguousSymbolError, SymbolNotFoundError

logger = logging.getLogger(__name__)

# JSON-RPC 2.0 error codes
_PARSE_ERROR      = -32700
_INVALID_REQUEST  = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS   = -32602
_INTERNAL_ERROR   = -32603

router = APIRouter(tags=["jsonrpc"])


def _error(id: Any, code: int, message: str, data: Any = None) -> dict:
    err: dict = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": err}


def _ok(id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


async def _dispatch(method: str, params: dict | list | None, req_id: Any) -> dict:
    p = params if isinstance(params, dict) else {}

    try:
        if method == "instruments.list":
            from market_data.api.rest.instruments import list_instruments
            from fastapi.testclient import TestClient  # noqa: F401 — not used here
            # Call the business logic directly instead of going through HTTP
            return _ok(req_id, await _instruments_list(p))

        elif method == "instruments.get":
            symbol = p.get("symbol")
            if not symbol:
                return _error(req_id, _INVALID_PARAMS, "Missing 'symbol'")
            return _ok(req_id, await _instrument_get(symbol))

        elif method == "instruments.fundamentals":
            symbol = p.get("symbol")
            if not symbol:
                return _error(req_id, _INVALID_PARAMS, "Missing 'symbol'")
            return _ok(req_id, await _instrument_fundamentals(symbol))

        elif method == "ohlcv.get":
            symbol = p.get("symbol")
            if not symbol:
                return _error(req_id, _INVALID_PARAMS, "Missing 'symbol'")
            return _ok(req_id, await _ohlcv_get(p))

        else:
            return _error(req_id, _METHOD_NOT_FOUND, f"Method not found: {method!r}")

    except SymbolNotFoundError as exc:
        return _error(req_id, _INVALID_PARAMS, str(exc))
    except AmbiguousSymbolError as exc:
        return _error(req_id, _INVALID_PARAMS, str(exc), exc.matches)
    except ValidationError as exc:
        return _error(req_id, _INVALID_PARAMS, "Validation error", exc.errors())
    except Exception as exc:
        logger.exception("JSON-RPC internal error for method %s: %s", method, exc)
        return _error(req_id, _INTERNAL_ERROR, "Internal error")


async def _instruments_list(p: dict) -> dict:
    from market_data.db.connection import get_connection
    from market_data.models.enums import AssetClass
    conn = get_connection()
    conditions = ["is_active = ?"]
    params: list = [p.get("is_active", True)]
    asset_class = p.get("asset_class")
    if asset_class:
        conditions.append("asset_class = ?")
        params.append(asset_class)
    q = p.get("q")
    if q:
        conditions.append("(upper(ticker) LIKE upper(?) OR upper(full_name) LIKE upper(?))")
        pattern = f"%{q}%"
        params.extend([pattern, pattern])
    page = int(p.get("page", 1))
    page_size = int(p.get("page_size", 50))
    offset = (page - 1) * page_size
    where = " AND ".join(conditions)
    total = conn.execute(f"SELECT COUNT(*) FROM instruments WHERE {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT instrument_id, ticker, full_name, asset_class, exchange FROM instruments WHERE {where} ORDER BY ticker LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()
    cols = ["instrument_id", "ticker", "full_name", "asset_class", "exchange"]
    return {"total": total, "page": page, "page_size": page_size, "items": [dict(zip(cols, r)) for r in rows]}


async def _instrument_get(symbol: str) -> dict:
    from market_data.db.resolver import resolve_symbol
    from market_data.db.connection import get_connection
    instrument_id = resolve_symbol(symbol)
    conn = get_connection()
    row = conn.execute(
        "SELECT instrument_id, ticker, full_name, asset_class, exchange, is_active FROM instruments WHERE instrument_id = ?",
        [instrument_id],
    ).fetchone()
    if not row:
        raise SymbolNotFoundError(symbol)
    return dict(zip(["instrument_id", "ticker", "full_name", "asset_class", "exchange", "is_active"], row))


async def _instrument_fundamentals(symbol: str) -> dict:
    from market_data.db.resolver import resolve_symbol
    from market_data.db.connection import get_connection
    instrument_id = resolve_symbol(symbol)
    conn = get_connection()
    base = conn.execute("SELECT instrument_id, asset_class FROM instruments WHERE instrument_id = ?", [instrument_id]).fetchone()
    if not base:
        raise SymbolNotFoundError(symbol)
    return {"instrument_id": base[0], "asset_class": base[1]}


async def _ohlcv_get(p: dict) -> dict:
    from market_data.db.resolver import resolve_symbol
    from market_data.db.connection import get_connection
    from market_data.models.enums import Interval, AssetClass
    from datetime import timezone
    symbol = p["symbol"]
    interval = p.get("interval", "1d")
    asset_class = p.get("asset_class")
    since = p.get("since")
    until = p.get("until")
    page = int(p.get("page", 1))
    page_size = int(p.get("page_size", 1000))

    instrument_id = resolve_symbol(symbol, AssetClass(asset_class) if asset_class else None)
    conn = get_connection()
    conditions = ["instrument_id = ?", "interval = ?"]
    params: list = [instrument_id, interval]
    if since:
        from datetime import datetime
        conditions.append("ts >= ?")
        params.append(datetime.fromisoformat(since.replace("Z", "+00:00")))
    if until:
        from datetime import datetime
        conditions.append("ts <= ?")
        params.append(datetime.fromisoformat(until.replace("Z", "+00:00")))
    where = " AND ".join(conditions)
    offset = (page - 1) * page_size
    total = conn.execute(f"SELECT COUNT(*) FROM ohlcv WHERE {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT instrument_id, interval, ts, open, high, low, close, volume FROM ohlcv WHERE {where} ORDER BY ts ASC LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()
    cols = ["instrument_id", "interval", "ts", "open", "high", "low", "close", "volume"]
    return {"total": total, "page": page, "page_size": page_size, "items": [dict(zip(cols, r)) for r in rows]}


@router.post("")
async def jsonrpc_handler(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content=_error(None, _PARSE_ERROR, "Parse error"),
            status_code=200,
        )

    # Batch request
    if isinstance(body, list):
        responses = []
        for item in body:
            if not isinstance(item, dict):
                responses.append(_error(None, _INVALID_REQUEST, "Invalid Request"))
                continue
            method = item.get("method", "")
            params = item.get("params")
            req_id = item.get("id")
            responses.append(await _dispatch(method, params, req_id))
        return JSONResponse(content=responses, status_code=200)

    # Single request
    if not isinstance(body, dict):
        return JSONResponse(
            content=_error(None, _INVALID_REQUEST, "Invalid Request"),
            status_code=200,
        )
    method = body.get("method", "")
    params = body.get("params")
    req_id = body.get("id")
    result = await _dispatch(method, params, req_id)
    return JSONResponse(content=result, status_code=200)
