"""best_sma_exit_v1 strategy — BEST SMA with explicit TP exits.

This strategy is additive and does not modify `best_sma` behavior.
"""
from __future__ import annotations

from market_data.db.connection import get_connection
from market_data.strategies.backtest import sma
from market_data.strategies.backtest_exit_v1 import (
    backtest_long_strategy_exit_v1,
    backtest_short_strategy_exit_v1,
)

_SMA_MIN = 3
_SMA_MAX = 50


def _load_daily_candles_from_hourly(instrument_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """
        WITH daily AS (
            SELECT
                DATE_TRUNC('day', ts)                        AS day,
                MIN(ts)                                      AS first_ts,
                MAX(ts)                                      AS last_ts,
                MAX(high)                                    AS high,
                MIN(low)                                     AS low,
                SUM(volume)                                  AS volume
            FROM ohlcv
            WHERE instrument_id = %s AND interval = '1h'
            GROUP BY DATE_TRUNC('day', ts)
        )
        SELECT
            d.day,
            o_open.open,
            d.high,
            d.low,
            o_close.close
        FROM daily d
        JOIN ohlcv o_open  ON o_open.instrument_id  = %s
                          AND o_open.interval        = '1h'
                          AND o_open.ts              = d.first_ts
        JOIN ohlcv o_close ON o_close.instrument_id = %s
                          AND o_close.interval       = '1h'
                          AND o_close.ts             = d.last_ts
        ORDER BY d.day ASC
        """,
        [instrument_id, instrument_id, instrument_id],
    ).fetchall()

    if not rows:
        raise ValueError(
            f"No hourly OHLCV data found for instrument_id={instrument_id!r}. "
            "Run 'import-ohlcv --interval 1h' before computing indicators."
        )

    return [
        {"date": str(r[0])[:10], "open": r[1], "high": r[2], "low": r[3], "close": r[4]}
        for r in rows
    ]


def _parameters(parameters: dict | None) -> tuple[float, float, float, float]:
    params = parameters or {}
    sl_short = float(params.get("sl_short", 10.0)) / 100.0
    sl_long = float(params.get("sl_long", 10.0)) / 100.0
    pos_usd = float(params.get("pos_usd", 100.0))
    tp_pct = float(params.get("tp_pct", 5.0)) / 100.0
    return sl_short, sl_long, pos_usd, tp_pct


def run_backtest_best_sma_exit_v1(
    instrument_id: str,
    parameters: dict | None = None,
    sma_low_period: int | None = None,
    sma_high_period: int | None = None,
) -> dict:
    """Run backtest for the v1 exit strategy and return summary + trades."""
    sl_short, sl_long, pos_usd, tp_pct = _parameters(parameters)
    candles = _load_daily_candles_from_hourly(instrument_id)

    lows = [c["low"] for c in candles]
    highs = [c["high"] for c in candles]

    low_p = sma_low_period if sma_low_period is not None else _SMA_MIN
    high_p = sma_high_period if sma_high_period is not None else _SMA_MIN

    if not (_SMA_MIN <= low_p <= _SMA_MAX):
        raise ValueError(f"sma_low_period must be between {_SMA_MIN} and {_SMA_MAX}")
    if not (_SMA_MIN <= high_p <= _SMA_MAX):
        raise ValueError(f"sma_high_period must be between {_SMA_MIN} and {_SMA_MAX}")

    sma_low = sma(lows, low_p)
    sma_high = sma(highs, high_p)

    short_trades = backtest_short_strategy_exit_v1(
        candles,
        sma_low,
        position_size_usd=pos_usd,
        stop_loss_pct=sl_short,
        take_profit_pct=tp_pct,
    )
    long_trades = backtest_long_strategy_exit_v1(
        candles,
        sma_high,
        position_size_usd=pos_usd,
        stop_loss_pct=sl_long,
        take_profit_pct=tp_pct,
    )

    all_trades = sorted(
        short_trades + long_trades,
        key=lambda t: (str(t.get("entry_date") or ""), int(t.get("entry_idx") or 0)),
    )

    closed = [t for t in all_trades if not t.get("is_open") and t.get("pnl") is not None]
    total_pnl = float(sum(float(t["pnl"]) for t in closed)) if closed else 0.0
    avg_pnl = (total_pnl / len(closed)) if closed else 0.0

    return {
        "sma_low": low_p,
        "sma_high": high_p,
        "summary": {
            "total_trades": len(all_trades),
            "closed_trades": len(closed),
            "open_trades": len(all_trades) - len(closed),
            "total_pnl": total_pnl,
            "avg_closed_pnl": avg_pnl,
            "tp_pct": tp_pct,
            "sl_short": sl_short,
            "sl_long": sl_long,
            "pos_usd": pos_usd,
        },
        "trades": all_trades,
    }


def compute_best_sma_exit_v1(instrument_id: str, parameters: dict | None = None) -> dict[str, int]:
    """Find the best SMA pair for the enhanced exit strategy using train split."""
    sl_short, sl_long, pos_usd, tp_pct = _parameters(parameters)
    candles = _load_daily_candles_from_hourly(instrument_id)

    split_idx = max(1, int(len(candles) * 0.8))
    train = candles[:split_idx]

    lows = [c["low"] for c in train]
    highs = [c["high"] for c in train]

    sma_low_arrays = {p: sma(lows, p) for p in range(_SMA_MIN, _SMA_MAX + 1)}
    sma_high_arrays = {p: sma(highs, p) for p in range(_SMA_MIN, _SMA_MAX + 1)}

    best_score = float("-inf")
    best_pair = (_SMA_MIN, _SMA_MIN)

    for sma_low_p in range(_SMA_MIN, _SMA_MAX + 1):
        short_trades = backtest_short_strategy_exit_v1(
            train,
            sma_low_arrays[sma_low_p],
            position_size_usd=pos_usd,
            stop_loss_pct=sl_short,
            take_profit_pct=tp_pct,
        )
        for sma_high_p in range(_SMA_MIN, _SMA_MAX + 1):
            long_trades = backtest_long_strategy_exit_v1(
                train,
                sma_high_arrays[sma_high_p],
                position_size_usd=pos_usd,
                stop_loss_pct=sl_long,
                take_profit_pct=tp_pct,
            )
            closed_pnl = sum(
                t["pnl"] for t in short_trades if not t["is_open"] and t["pnl"] is not None
            ) + sum(
                t["pnl"] for t in long_trades if not t["is_open"] and t["pnl"] is not None
            )
            n_closed = sum(
                1 for t in short_trades if not t["is_open"] and t["pnl"] is not None
            ) + sum(
                1 for t in long_trades if not t["is_open"] and t["pnl"] is not None
            )
            score = closed_pnl / n_closed if n_closed > 0 else float("-inf")
            if score > best_score:
                best_score = score
                best_pair = (sma_low_p, sma_high_p)

    return {"sma_low": best_pair[0], "sma_high": best_pair[1]}
