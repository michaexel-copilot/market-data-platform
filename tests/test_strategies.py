"""Unit and integration tests for the strategy engine."""
from __future__ import annotations

import duckdb
import pytest
from pathlib import Path

from market_data.strategies.backtest import sma, backtest_short_strategy, backtest_long_strategy

MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "market_data" / "db" / "migrations"


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


# ---------------------------------------------------------------------------
# compute_best_sma()
# ---------------------------------------------------------------------------

@pytest.fixture
def db_with_ohlcv():
    """In-memory DB with migrations + BTC instrument + 200 days of hourly candles (2 rows per day)."""
    import random
    import datetime
    import market_data.db.connection as cm

    conn = duckdb.connect(":memory:")
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.execute(f.read_text())
    conn.execute(
        "INSERT INTO instruments (instrument_id, ticker, exchange, asset_class, is_active) "
        "VALUES ('uuid-btc-001', 'BTC', 'BINANCE', 'crypto', TRUE)"
    )
    rng = random.Random(42)
    price = 40000.0
    for i in range(200):
        day = datetime.date(2024, 1, 1) + datetime.timedelta(days=i)
        price *= 1 + rng.uniform(-0.03, 0.03)
        h, l = price * 1.01, price * 0.99
        ts_open  = datetime.datetime.combine(day, datetime.time(0, 0, 0))
        ts_close = datetime.datetime.combine(day, datetime.time(23, 0, 0))
        conn.execute(
            "INSERT INTO ohlcv (instrument_id,interval,ts,open,high,low,close,volume,source) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ["uuid-btc-001", "1h", str(ts_open), price * 0.995, h, l, price, 500, "test"],
        )
        conn.execute(
            "INSERT INTO ohlcv (instrument_id,interval,ts,open,high,low,close,volume,source) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ["uuid-btc-001", "1h", str(ts_close), price * 0.995, h, l, price * 1.005, 500, "test"],
        )
    original = cm._conn
    cm._conn = conn
    yield conn
    conn.close()
    cm._conn = original


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
