"""Pure backtest primitives — ported from FindShortOpportunites/draw_chart.py."""
from __future__ import annotations


def sma(values: list[float], period: int) -> list[float | None]:
    """Simple moving average. Returns None for the first (period-1) entries."""
    result: list[float | None] = [None] * (period - 1)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        result.append(sum(window) / period)
    return result


def backtest_short_strategy(
    candles: list[dict],
    sma_low: list[float | None],
    position_size_usd: float = 100.0,
    stop_loss_pct: float = 0.10,
) -> list[dict]:
    """Short strategy backtest on daily candle data.

    Entry  : close crosses below sma_low (was >= yesterday, now <).
    Stop   : close >= entry × (1 + stop_loss_pct)  → exit at stop price (loss).
    Profit : close >= sma_low[i] AND sma_low[i] < entry_price → exit at sma_low[i].
    No new entry while a position is open. Returns all trades (incl. open).
    """
    trades: list[dict] = []
    in_position = False
    entry_trade: dict | None = None
    _running_max_upnl: float = 0.0
    _running_min_upnl: float = 0.0

    for i in range(1, len(candles)):
        sl_prev = sma_low[i - 1]
        sl_curr = sma_low[i]
        if sl_prev is None or sl_curr is None:
            continue
        c_curr = candles[i]
        c_prev = candles[i - 1]

        if not in_position:
            if c_prev["close"] >= sl_prev and c_curr["close"] < sl_curr:
                entry_price = c_curr["close"]
                entry_trade = {
                    "entry_date":  c_curr["date"],
                    "entry_price": entry_price,
                    "stop_loss":   entry_price * (1 + stop_loss_pct),
                    "entry_idx":   i,
                    "exit_date":   None,
                    "exit_price":  None,
                    "exit_idx":    None,
                    "pnl":         None,
                    "is_open":     True,
                }
                _running_max_upnl = float("-inf")
                _running_min_upnl = float("inf")
                in_position = True
        else:
            assert entry_trade is not None
            upnl = (
                (entry_trade["entry_price"] - c_curr["close"])
                / entry_trade["entry_price"]
                * position_size_usd
            )
            if upnl > _running_max_upnl:
                _running_max_upnl = upnl
            if upnl < _running_min_upnl:
                _running_min_upnl = upnl
            if c_curr["close"] >= entry_trade["stop_loss"]:
                exit_price = entry_trade["stop_loss"]
                entry_trade.update({
                    "exit_date":  c_curr["date"],
                    "exit_price": exit_price,
                    "exit_idx":   i,
                    "pnl": (entry_trade["entry_price"] - exit_price)
                           / entry_trade["entry_price"] * position_size_usd,
                    "is_open": False,
                    "max_adverse_pnl":    _running_min_upnl,
                    "max_favourable_pnl": _running_max_upnl,
                })
                trades.append(entry_trade)
                entry_trade = None
                in_position = False
            elif c_curr["close"] >= sl_curr and sl_curr < entry_trade["entry_price"]:
                exit_price = sl_curr
                entry_trade.update({
                    "exit_date":  c_curr["date"],
                    "exit_price": exit_price,
                    "exit_idx":   i,
                    "pnl": (entry_trade["entry_price"] - exit_price)
                           / entry_trade["entry_price"] * position_size_usd,
                    "is_open": False,
                    "max_adverse_pnl":    _running_min_upnl,
                    "max_favourable_pnl": _running_max_upnl,
                })
                trades.append(entry_trade)
                entry_trade = None
                in_position = False

    if in_position and entry_trade:
        entry_trade["max_adverse_pnl"] = None
        entry_trade["max_favourable_pnl"] = None
        trades.append(entry_trade)

    return trades


def backtest_long_strategy(
    candles: list[dict],
    sma_high: list[float | None],
    position_size_usd: float = 100.0,
    stop_loss_pct: float = 0.10,
) -> list[dict]:
    """Long strategy backtest on daily candle data — mirror of the short strategy.

    Entry  : close crosses above sma_high (was <= yesterday, now >).
    Stop   : close <= entry × (1 - stop_loss_pct) → exit at stop price (loss).
    Profit : sma_high[i] > entry_price AND close[i] <= sma_high[i] → exit at sma_high[i].
    No new entry while a position is open. Returns all trades (incl. open).
    """
    trades: list[dict] = []
    in_position = False
    entry_trade: dict | None = None
    _running_max_upnl: float = 0.0
    _running_min_upnl: float = 0.0

    for i in range(1, len(candles)):
        sh_prev = sma_high[i - 1]
        sh_curr = sma_high[i]
        if sh_prev is None or sh_curr is None:
            continue
        c_curr = candles[i]
        c_prev = candles[i - 1]

        if not in_position:
            if c_prev["close"] <= sh_prev and c_curr["close"] > sh_curr:
                entry_price = c_curr["close"]
                entry_trade = {
                    "entry_date":  c_curr["date"],
                    "entry_price": entry_price,
                    "stop_loss":   entry_price * (1 - stop_loss_pct),
                    "entry_idx":   i,
                    "exit_date":   None,
                    "exit_price":  None,
                    "exit_idx":    None,
                    "pnl":         None,
                    "is_open":     True,
                }
                _running_max_upnl = float("-inf")
                _running_min_upnl = float("inf")
                in_position = True
        else:
            assert entry_trade is not None
            upnl = (
                (c_curr["close"] - entry_trade["entry_price"])
                / entry_trade["entry_price"]
                * position_size_usd
            )
            if upnl > _running_max_upnl:
                _running_max_upnl = upnl
            if upnl < _running_min_upnl:
                _running_min_upnl = upnl
            if c_curr["close"] <= entry_trade["stop_loss"]:
                exit_price = entry_trade["stop_loss"]
                entry_trade.update({
                    "exit_date":  c_curr["date"],
                    "exit_price": exit_price,
                    "exit_idx":   i,
                    "pnl": (exit_price - entry_trade["entry_price"])
                           / entry_trade["entry_price"] * position_size_usd,
                    "is_open": False,
                    "max_adverse_pnl":    _running_min_upnl,
                    "max_favourable_pnl": _running_max_upnl,
                })
                trades.append(entry_trade)
                entry_trade = None
                in_position = False
            elif sh_curr > entry_trade["entry_price"] and c_curr["close"] <= sh_curr:
                exit_price = sh_curr
                entry_trade.update({
                    "exit_date":  c_curr["date"],
                    "exit_price": exit_price,
                    "exit_idx":   i,
                    "pnl": (exit_price - entry_trade["entry_price"])
                           / entry_trade["entry_price"] * position_size_usd,
                    "is_open": False,
                    "max_adverse_pnl":    _running_min_upnl,
                    "max_favourable_pnl": _running_max_upnl,
                })
                trades.append(entry_trade)
                entry_trade = None
                in_position = False

    if in_position and entry_trade:
        entry_trade["max_adverse_pnl"] = None
        entry_trade["max_favourable_pnl"] = None
        trades.append(entry_trade)

    return trades
