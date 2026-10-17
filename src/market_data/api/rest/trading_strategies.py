"""REST trading-strategies router."""
from __future__ import annotations

import datetime as dt
import json

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from market_data.db.connection import get_connection
from market_data.models.api import SymbolNotFoundError
from market_data.strategies.backtest import sma
from market_data.strategies.registry import STRATEGY_REGISTRY

router = APIRouter(prefix="/v1/trading-strategies", tags=["trading-strategies"])
_V2_STRATEGY = "best_sma_exit_v1"


class ComputeRequest(BaseModel):
    strategy: str
    sl_short: float = 10.0
    sl_long: float = 10.0
    pos_usd: float = 100.0


class ComputeV2Request(BaseModel):
    sl_short: float = 10.0
    sl_long: float = 10.0
    tp_pct: float = 5.0
    pos_usd: float = 100.0


class BacktestV2Request(BaseModel):
    sl_short: float = 10.0
    sl_long: float = 10.0
    tp_pct: float = 5.0
    pos_usd: float = 100.0
    sma_low_period: int | None = Field(default=None, ge=3, le=50)
    sma_high_period: int | None = Field(default=None, ge=3, le=50)
    max_trades: int = Field(default=500, ge=1, le=10000)


def _persist_indicators(conn, instrument_id: str, strategy_name: str, parameters: dict, indicators: dict) -> None:
    params_json = json.dumps(parameters)
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


def _parse_trade_context_date(trade: dict) -> dt.date | None:
    for key in ("opened_trade_ts", "entry_date", "opened_at"):
        value = trade.get(key)
        if not value:
            continue
        if isinstance(value, dt.datetime):
            return value.date()
        if isinstance(value, dt.date):
            return value
        text = str(value).strip()
        if not text:
            continue
        try:
            if "T" in text:
                return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).date()
            return dt.date.fromisoformat(text[:10])
        except ValueError:
            continue
    return None


def _select_chart_window(trades: list[dict], available_dates: list[dt.date]) -> tuple[str, dt.date, dt.date]:
    today = dt.date.today()
    last_available = max(available_dates) if available_dates else today
    end = today if last_available >= (today - dt.timedelta(days=7)) else last_available

    opened_trade = None
    for trade in trades:
        opened_trade = _parse_trade_context_date(trade)
        if opened_trade is not None:
            break

    if opened_trade is not None:
        start = min(opened_trade - dt.timedelta(days=5), end - dt.timedelta(days=29))
        mode = "trade_context"
    else:
        start = end - dt.timedelta(days=29)
        mode = "fallback_30d"

    if available_dates and not any(start <= day <= end for day in available_dates):
        end = last_available
        if opened_trade is not None:
            start = min(opened_trade - dt.timedelta(days=5), end - dt.timedelta(days=29))
            mode = "trade_context"
        else:
            start = end - dt.timedelta(days=29)
            mode = "fallback_30d"

    return mode, start, end


def _align_chart_series(
    candles: list[dict],
    sma_low_series: list[float | None],
    sma_high_series: list[float | None],
    start: dt.date,
    end: dt.date,
) -> tuple[list[str], list[float], list[float | None], list[float | None]]:
    aligned_dates: list[str] = []
    price: list[float] = []
    sma_low: list[float | None] = []
    sma_high: list[float | None] = []

    for idx, candle in enumerate(candles):
        candle_day = dt.date.fromisoformat(str(candle["date"])[:10])
        if candle_day < start or candle_day > end:
            continue
        aligned_dates.append(str(candle["date"])[:10])
        price.append(float(candle["close"]))
        sma_low.append(None if sma_low_series[idx] is None else float(sma_low_series[idx]))
        sma_high.append(None if sma_high_series[idx] is None else float(sma_high_series[idx]))

    if aligned_dates:
        return aligned_dates, price, sma_low, sma_high

    tail = candles[-30:]
    for idx, candle in enumerate(tail, start=max(0, len(candles) - len(tail))):
        aligned_dates.append(str(candle["date"])[:10])
        price.append(float(candle["close"]))
        sma_low.append(None if sma_low_series[idx] is None else float(sma_low_series[idx]))
        sma_high.append(None if sma_high_series[idx] is None else float(sma_high_series[idx]))
    return aligned_dates, price, sma_low, sma_high


def _build_performance_chart_payload(
    candles: list[dict],
    trades: list[dict],
    sma_low_period: int | None,
    sma_high_period: int | None,
) -> dict:
    if not candles:
        return {
            "mode": "fallback_30d",
            "start": dt.date.today().isoformat(),
            "end": dt.date.today().isoformat(),
            "dates": [],
            "price": [],
            "indicators": {"sma_low": [], "sma_high": []},
            "state": "empty",
        }

    lows = [float(c["low"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    sma_low_series = sma(lows, int(sma_low_period)) if sma_low_period else [None] * len(candles)
    sma_high_series = sma(highs, int(sma_high_period)) if sma_high_period else [None] * len(candles)

    available_dates = [dt.date.fromisoformat(str(c["date"])[:10]) for c in candles]
    mode, start, end = _select_chart_window(trades, available_dates)
    dates, price, sma_low_aligned, sma_high_aligned = _align_chart_series(
        candles,
        sma_low_series,
        sma_high_series,
        start,
        end,
    )

    indicators_missing = all(value is None for value in sma_low_aligned) and all(
        value is None for value in sma_high_aligned
    )

    return {
        "mode": mode,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "dates": dates,
        "price": price,
        "indicators": {
            "sma_low": sma_low_aligned,
            "sma_high": sma_high_aligned,
        },
        "state": "price_only" if indicators_missing else "price_and_indicators",
    }


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
    _persist_indicators(conn, instrument_id, body.strategy, parameters, indicators)

    computed = [
        {"indicator_name": k, "indicator_value": v} for k, v in indicators.items()
    ]
    return JSONResponse({"computed": computed})


@router.get("/{symbol}/v2")
async def get_trading_strategies_v2(symbol: str) -> JSONResponse:
    from market_data.db.resolver import resolve_symbol

    instrument_id = resolve_symbol(symbol)
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT strategy_name, indicator_name, indicator_value, parameters, computed_at
        FROM trading_strategies
        WHERE instrument_id = %s AND strategy_name = %s
        ORDER BY indicator_name
        """,
        [instrument_id, _V2_STRATEGY],
    ).fetchall()

    if not rows:
        return JSONResponse(
            status_code=404,
            content={
                "error": (
                    f"No precomputed indicators for {symbol} with strategy '{_V2_STRATEGY}'. "
                    "Run compute-v2 first."
                )
            },
        )

    items = [
        {
            "strategy_name": r[0],
            "indicator_name": r[1],
            "indicator_value": r[2],
            "parameters": json.loads(r[3]) if r[3] else None,
            "computed_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]
    return JSONResponse({"items": items})


@router.post("/{symbol}/compute-v2")
async def compute_trading_strategies_v2(symbol: str, body: ComputeV2Request) -> JSONResponse:
    from market_data.db.resolver import resolve_symbol

    instrument_id = resolve_symbol(symbol)
    strategy_fn = STRATEGY_REGISTRY[_V2_STRATEGY]
    parameters = {
        "sl_short": body.sl_short,
        "sl_long": body.sl_long,
        "tp_pct": body.tp_pct,
        "pos_usd": body.pos_usd,
    }

    try:
        indicators = strategy_fn(instrument_id, parameters)
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})

    conn = get_connection()
    _persist_indicators(conn, instrument_id, _V2_STRATEGY, parameters, indicators)

    computed = [{"indicator_name": k, "indicator_value": v} for k, v in indicators.items()]
    return JSONResponse({"strategy": _V2_STRATEGY, "computed": computed})


@router.post("/{symbol}/backtest-v2")
async def backtest_trading_strategies_v2(symbol: str, body: BacktestV2Request) -> JSONResponse:
    from market_data.db.resolver import resolve_symbol
    from market_data.strategies.best_sma_exit_v1 import (
        _load_daily_candles_from_hourly,
        run_backtest_best_sma_exit_v1,
    )

    instrument_id = resolve_symbol(symbol)
    parameters = {
        "sl_short": body.sl_short,
        "sl_long": body.sl_long,
        "tp_pct": body.tp_pct,
        "pos_usd": body.pos_usd,
    }

    sma_low_period = body.sma_low_period
    sma_high_period = body.sma_high_period
    if sma_low_period is None or sma_high_period is None:
        indicators = STRATEGY_REGISTRY[_V2_STRATEGY](instrument_id, parameters)
        sma_low_period = int(indicators["sma_low"])
        sma_high_period = int(indicators["sma_high"])

    try:
        result = run_backtest_best_sma_exit_v1(
            instrument_id,
            parameters,
            sma_low_period=sma_low_period,
            sma_high_period=sma_high_period,
        )
        candles = _load_daily_candles_from_hourly(instrument_id)
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})

    trades = result.get("trades", [])
    max_trades = int(body.max_trades)
    if len(trades) > max_trades:
        trades = trades[-max_trades:]

    chart = _build_performance_chart_payload(
        candles,
        trades,
        sma_low_period=sma_low_period,
        sma_high_period=sma_high_period,
    )

    return JSONResponse(
        {
            "strategy": _V2_STRATEGY,
            "sma_low": result.get("sma_low"),
            "sma_high": result.get("sma_high"),
            "summary": result.get("summary", {}),
            "trades": trades,
            "truncated": len(result.get("trades", [])) > max_trades,
            "chart": chart,
            "cached_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        }
    )
