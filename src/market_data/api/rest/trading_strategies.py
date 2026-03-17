"""REST trading-strategies router."""
from __future__ import annotations

import json

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from market_data.db.connection import get_connection
from market_data.models.api import SymbolNotFoundError
from market_data.strategies.registry import STRATEGY_REGISTRY

router = APIRouter(prefix="/v1/trading-strategies", tags=["trading-strategies"])


class ComputeRequest(BaseModel):
    strategy: str
    sl_short: float = 10.0
    sl_long: float = 10.0
    pos_usd: float = 100.0


@router.get("/{symbol}")
async def get_trading_strategies(
    symbol: str,
    strategy_name: str | None = Query(default=None),
) -> JSONResponse:
    from market_data.db.resolver import resolve_symbol
    instrument_id = resolve_symbol(symbol)

    conn = get_connection()
    conditions = ["instrument_id = %s"]
    params: list = [instrument_id]
    if strategy_name:
        conditions.append("strategy_name = %s")
        params.append(strategy_name)

    where = " AND ".join(conditions)
    rows = conn.execute(
        f"""
        SELECT strategy_name, indicator_name, indicator_value, parameters, computed_at
        FROM trading_strategies
        WHERE {where}
        ORDER BY strategy_name, indicator_name
        """,
        params,
    ).fetchall()

    if not rows:
        filter_hint = f" with strategy '{strategy_name}'" if strategy_name else ""
        return JSONResponse(
            status_code=404,
            content={
                "error": (
                    f"No precomputed indicators for {symbol}{filter_hint}. "
                    "Run compute-indicators --strategy <name> first."
                )
            },
        )

    items = [
        {
            "strategy_name":   r[0],
            "indicator_name":  r[1],
            "indicator_value": r[2],
            "parameters":      json.loads(r[3]) if r[3] else None,
            "computed_at":     r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]
    return JSONResponse({"items": items})


@router.post("/{symbol}/compute")
async def compute_trading_strategies(symbol: str, body: ComputeRequest) -> JSONResponse:
    from market_data.db.resolver import resolve_symbol
    instrument_id = resolve_symbol(symbol)

    if body.strategy not in STRATEGY_REGISTRY:
        available = ", ".join(sorted(STRATEGY_REGISTRY))
        return JSONResponse(
            status_code=422,
            content={"error": f"Unknown strategy {body.strategy!r}. Available: {available}"},
        )

    parameters = {
        "sl_short": body.sl_short,
        "sl_long":  body.sl_long,
        "pos_usd":  body.pos_usd,
    }
    strategy_fn = STRATEGY_REGISTRY[body.strategy]

    try:
        indicators = strategy_fn(instrument_id, parameters)
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})

    conn = get_connection()
    import json as _json
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
            [instrument_id, body.strategy, indicator_name, float(indicator_value), params_json],
        )

    computed = [
        {"indicator_name": k, "indicator_value": v} for k, v in indicators.items()
    ]
    return JSONResponse({"computed": computed})
