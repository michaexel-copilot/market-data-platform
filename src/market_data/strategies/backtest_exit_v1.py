"""Backtest primitives for best_sma_exit_v1 with enhanced TP exits.

This module intentionally does not modify existing backtest logic in
`market_data.strategies.backtest`.
"""
from __future__ import annotations


def backtest_short_strategy_exit_v1(
    candles: list[dict],
    sma_short: list[float | None],
    position_size_usd: float = 100.0,
    stop_loss_pct: float = 0.10,
    take_profit_pct: float = 0.05,
) -> list[dict]:
    """Short strategy with stop-loss, TP%% and SMA-rebound exits.

    Exit precedence on the same candle:
    1) stop_loss
    2) take_profit_pct
    3) take_profit_sma
    """
    trades: list[dict] = []
    in_position = False
    entry_trade: dict | None = None
    running_max_upnl = 0.0
    running_min_upnl = 0.0

    for i in range(1, len(candles)):
        ss_prev = sma_short[i - 1]
        ss_curr = sma_short[i]
        if ss_prev is None or ss_curr is None:
            continue

        c_prev = candles[i - 1]
        c_curr = candles[i]

        if not in_position:
            if c_prev["close"] >= ss_prev and c_curr["close"] < ss_curr:
                entry_price = c_curr["close"]
                entry_trade = {
                    "side": "short",
                    "entry_date": c_curr["date"],
                    "entry_price": entry_price,
                    "stop_loss": entry_price * (1 + stop_loss_pct),
                    "take_profit_target": entry_price * (1 - take_profit_pct),
                    "entry_idx": i,
                    "exit_date": None,
                    "exit_price": None,
                    "exit_idx": None,
                    "exit_reason": None,
                    "pnl": None,
                    "is_open": True,
                }
                running_max_upnl = float("-inf")
                running_min_upnl = float("inf")
                in_position = True
            continue

        assert entry_trade is not None
        upnl = (
            (entry_trade["entry_price"] - c_curr["close"])
            / entry_trade["entry_price"]
            * position_size_usd
        )
        if upnl > running_max_upnl:
            running_max_upnl = upnl
        if upnl < running_min_upnl:
            running_min_upnl = upnl

        if c_curr["close"] >= entry_trade["stop_loss"]:
            exit_price = entry_trade["stop_loss"]
            exit_reason = "stop_loss"
        elif c_curr["close"] <= entry_trade["take_profit_target"]:
            exit_price = entry_trade["take_profit_target"]
            exit_reason = "take_profit_pct"
        elif c_curr["close"] > ss_curr:
            exit_price = ss_curr
            exit_reason = "take_profit_sma"
        else:
            continue

        entry_trade.update(
            {
                "exit_date": c_curr["date"],
                "exit_price": exit_price,
                "exit_idx": i,
                "exit_reason": exit_reason,
                "pnl": (entry_trade["entry_price"] - exit_price)
                / entry_trade["entry_price"]
                * position_size_usd,
                "is_open": False,
                "max_adverse_pnl": running_min_upnl,
                "max_favourable_pnl": running_max_upnl,
            }
        )
        trades.append(entry_trade)
        entry_trade = None
        in_position = False

    if in_position and entry_trade:
        entry_trade["max_adverse_pnl"] = None
        entry_trade["max_favourable_pnl"] = None
        trades.append(entry_trade)

    return trades


def backtest_long_strategy_exit_v1(
    candles: list[dict],
    sma_long: list[float | None],
    position_size_usd: float = 100.0,
    stop_loss_pct: float = 0.10,
    take_profit_pct: float = 0.05,
) -> list[dict]:
    """Long strategy with stop-loss, TP%% and SMA-breakdown exits.

    Exit precedence on the same candle:
    1) stop_loss
    2) take_profit_pct
    3) take_profit_sma
    """
    trades: list[dict] = []
    in_position = False
    entry_trade: dict | None = None
    running_max_upnl = 0.0
    running_min_upnl = 0.0

    for i in range(1, len(candles)):
        sl_prev = sma_long[i - 1]
        sl_curr = sma_long[i]
        if sl_prev is None or sl_curr is None:
            continue

        c_prev = candles[i - 1]
        c_curr = candles[i]

        if not in_position:
            if c_prev["close"] <= sl_prev and c_curr["close"] > sl_curr:
                entry_price = c_curr["close"]
                entry_trade = {
                    "side": "long",
                    "entry_date": c_curr["date"],
                    "entry_price": entry_price,
                    "stop_loss": entry_price * (1 - stop_loss_pct),
                    "take_profit_target": entry_price * (1 + take_profit_pct),
                    "entry_idx": i,
                    "exit_date": None,
                    "exit_price": None,
                    "exit_idx": None,
                    "exit_reason": None,
                    "pnl": None,
                    "is_open": True,
                }
                running_max_upnl = float("-inf")
                running_min_upnl = float("inf")
                in_position = True
            continue

        assert entry_trade is not None
        upnl = (
            (c_curr["close"] - entry_trade["entry_price"])
            / entry_trade["entry_price"]
            * position_size_usd
        )
        if upnl > running_max_upnl:
            running_max_upnl = upnl
        if upnl < running_min_upnl:
            running_min_upnl = upnl

        if c_curr["close"] <= entry_trade["stop_loss"]:
            exit_price = entry_trade["stop_loss"]
            exit_reason = "stop_loss"
        elif c_curr["close"] >= entry_trade["take_profit_target"]:
            exit_price = entry_trade["take_profit_target"]
            exit_reason = "take_profit_pct"
        elif c_curr["close"] < sl_curr:
            exit_price = sl_curr
            exit_reason = "take_profit_sma"
        else:
            continue

        entry_trade.update(
            {
                "exit_date": c_curr["date"],
                "exit_price": exit_price,
                "exit_idx": i,
                "exit_reason": exit_reason,
                "pnl": (exit_price - entry_trade["entry_price"])
                / entry_trade["entry_price"]
                * position_size_usd,
                "is_open": False,
                "max_adverse_pnl": running_min_upnl,
                "max_favourable_pnl": running_max_upnl,
            }
        )
        trades.append(entry_trade)
        entry_trade = None
        in_position = False

    if in_position and entry_trade:
        entry_trade["max_adverse_pnl"] = None
        entry_trade["max_favourable_pnl"] = None
        trades.append(entry_trade)

    return trades
