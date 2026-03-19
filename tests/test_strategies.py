"""Unit and integration tests for the strategy engine."""
from __future__ import annotations

import pytest

from market_data.strategies.backtest import sma, backtest_short_strategy, backtest_long_strategy
from market_data.strategies.backtest_exit_v1 import (
    backtest_long_strategy_exit_v1,
    backtest_short_strategy_exit_v1,
)


# ---------------------------------------------------------------------------
# sma()
# ---------------------------------------------------------------------------

def test_sma_normal():
    result = sma([1.0, 2.0, 3.0, 4.0, 5.0], 3)
    assert result[:2] == [None, None]
    assert result[2] == pytest.approx(2.0)
    assert result[3] == pytest.approx(3.0)
    assert result[4] == pytest.approx(4.0)


def test_sma_period_1():
    values = [10.0, 20.0, 30.0]
    result = sma(values, 1)
    assert result == pytest.approx(values)


def test_sma_length_preserved():
    values = list(range(10))
    assert len(sma(values, 5)) == len(values)


# ---------------------------------------------------------------------------
# backtest_short_strategy()
# ---------------------------------------------------------------------------

def _make_candles(closes: list[float], highs: list[float] | None = None, lows: list[float] | None = None) -> list[dict]:
    if highs is None:
        highs = [c * 1.01 for c in closes]
    if lows is None:
        lows = [c * 0.99 for c in closes]
    return [
        {"date": f"2024-01-{i+1:02d}", "open": c, "high": h, "low": l, "close": c}
        for i, (c, h, l) in enumerate(zip(closes, highs, lows))
    ]


def test_short_no_trades_when_price_always_above_sma():
    # price stays above a flat SMA — no entry fires
    closes = [100.0] * 20
    candles = _make_candles(closes)
    sma_vals = [95.0] * 20  # SMA always below close
    trades = backtest_short_strategy(candles, sma_vals, position_size_usd=100.0, stop_loss_pct=0.10)
    assert trades == []


def test_short_entry_fires_on_cross_below():
    # close crosses from above SMA to below SMA at index 5
    closes = [100.0] * 5 + [90.0] * 10
    sma_vals = [95.0] * 15
    candles = _make_candles(closes)
    trades = backtest_short_strategy(candles, sma_vals)
    assert len(trades) >= 1
    assert trades[0]["entry_price"] == pytest.approx(90.0)


def test_short_stop_loss_triggers():
    # price spikes above entry * (1 + 0.10)
    closes = [100.0, 100.0, 90.0, 130.0]  # entry at 90, stop at 99
    sma_vals = [95.0, 95.0, 95.0, 95.0]
    candles = _make_candles(closes)
    trades = backtest_short_strategy(candles, sma_vals, position_size_usd=100.0, stop_loss_pct=0.10)
    closed = [t for t in trades if not t["is_open"]]
    assert len(closed) >= 1
    assert closed[0]["pnl"] < 0  # stop-loss = loss


def test_short_no_double_entry():
    # Rapid down-crosses — only one entry while position is open
    closes = [100, 90, 80, 70, 60, 50, 40]
    sma_vals = [95, 95, 85, 75, 65, 55, 45]
    candles = _make_candles(closes)
    trades = backtest_short_strategy(candles, sma_vals)
    open_trades = [t for t in trades if t["is_open"]]
    assert len(open_trades) <= 1


# ---------------------------------------------------------------------------
# backtest_long_strategy()
# ---------------------------------------------------------------------------

def test_long_entry_fires_on_cross_above():
    closes = [80.0] * 5 + [110.0] * 10
    sma_vals = [95.0] * 15
    candles = _make_candles(closes)
    trades = backtest_long_strategy(candles, sma_vals)
    assert len(trades) >= 1
    assert trades[0]["entry_price"] == pytest.approx(110.0)


def test_long_stop_loss_triggers():
    closes = [80.0, 80.0, 110.0, 60.0]  # entry at 110, stop at 99
    sma_vals = [95.0, 95.0, 95.0, 95.0]
    candles = _make_candles(closes)
    trades = backtest_long_strategy(candles, sma_vals, position_size_usd=100.0, stop_loss_pct=0.10)
    closed = [t for t in trades if not t["is_open"]]
    assert len(closed) >= 1
    assert closed[0]["pnl"] < 0


def test_short_take_profit_pct_triggers_before_sma_exit():
    closes = [100.0, 95.0, 84.0, 90.0]
    sma_vals = [97.0, 97.0, 90.0, 89.0]
    candles = _make_candles(closes)
    trades = backtest_short_strategy_exit_v1(
        candles,
        sma_vals,
        position_size_usd=100.0,
        stop_loss_pct=0.10,
        take_profit_pct=0.10,
    )
    closed = [t for t in trades if not t["is_open"]]
    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "take_profit_pct"


def test_long_take_profit_sma_triggers_on_close_below_sma():
    closes = [80.0, 110.0, 112.0, 106.0]
    sma_vals = [95.0, 95.0, 108.0, 108.0]
    candles = _make_candles(closes)
    trades = backtest_long_strategy_exit_v1(
        candles,
        sma_vals,
        position_size_usd=100.0,
        stop_loss_pct=0.10,
        take_profit_pct=0.30,
    )
    closed = [t for t in trades if not t["is_open"]]
    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "take_profit_sma"
    assert closed[0]["pnl"] is not None


# ---------------------------------------------------------------------------
# compute_best_sma()
# ---------------------------------------------------------------------------

@pytest.fixture
def db_with_ohlcv(db_conn):
    """Migrate + seed BTC instrument + 200 days of hourly candles (2 rows per day)."""
    import random
    import datetime

    db_conn.execute(
        "INSERT INTO instruments (instrument_id, ticker, exchange, asset_class, is_active)"
        " VALUES ('uuid-btc-001', 'BTC', 'BINANCE', 'crypto', TRUE)"
    )
    rng = random.Random(42)
    price = 40000.0
    insert_sql = (
        "INSERT INTO ohlcv (instrument_id, interval, ts, open, high, low, close, volume, source)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    for i in range(200):
        day = datetime.date(2024, 1, 1) + datetime.timedelta(days=i)
        price *= 1 + rng.uniform(-0.03, 0.03)
        h, l = price * 1.01, price * 0.99
        ts_open  = datetime.datetime.combine(day, datetime.time(0, 0, 0))
        ts_close = datetime.datetime.combine(day, datetime.time(23, 0, 0))
        db_conn.execute(insert_sql, ["uuid-btc-001", "1h", str(ts_open), price * 0.995, h, l, price, 500, "test"])
        db_conn.execute(insert_sql, ["uuid-btc-001", "1h", str(ts_close), price * 0.995, h, l, price * 1.005, 500, "test"])
    yield db_conn


def test_compute_best_sma_returns_valid_pair(db_with_ohlcv):
    from market_data.strategies.best_sma import compute_best_sma
    result = compute_best_sma("uuid-btc-001", {"sl_short": 10, "sl_long": 10, "pos_usd": 100})
    assert "sma_low" in result and "sma_high" in result
    assert 3 <= result["sma_low"] <= 50
    assert 3 <= result["sma_high"] <= 50


def test_compute_best_sma_raises_on_empty_ohlcv(db_with_ohlcv):
    from market_data.strategies.best_sma import compute_best_sma
    with pytest.raises(ValueError, match="No hourly OHLCV data"):
        compute_best_sma("nonexistent-uuid", {})


def test_strategy_registry_contains_best_sma(db_with_ohlcv):
    from market_data.strategies.registry import STRATEGY_REGISTRY
    assert "best_sma" in STRATEGY_REGISTRY
    result = STRATEGY_REGISTRY["best_sma"]("uuid-btc-001", {})
    assert "sma_low" in result


def test_compute_best_sma_exit_v1_returns_valid_pair(db_with_ohlcv):
    from market_data.strategies.best_sma_exit_v1 import compute_best_sma_exit_v1

    result = compute_best_sma_exit_v1(
        "uuid-btc-001",
        {"sl_short": 10, "sl_long": 10, "tp_pct": 5, "pos_usd": 100},
    )
    assert "sma_low" in result and "sma_high" in result
    assert 3 <= result["sma_low"] <= 50
    assert 3 <= result["sma_high"] <= 50


def test_strategy_registry_contains_best_sma_exit_v1(db_with_ohlcv):
    from market_data.strategies.registry import STRATEGY_REGISTRY

    assert "best_sma_exit_v1" in STRATEGY_REGISTRY
    result = STRATEGY_REGISTRY["best_sma_exit_v1"]("uuid-btc-001", {})
    assert "sma_low" in result
