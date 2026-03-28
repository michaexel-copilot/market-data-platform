"""
backtest_engine.py — backtesting.py-powered crossover strategy engine.

Provides:
  - candles_to_df()          : convert list[dict] candles → pandas DataFrame
  - LongCashStrategy         : go long on ind1 > ind2 crossover, exit on reversal
  - ShortCashStrategy        : go short on ind1 < ind2 crossover, exit on reversal
  - LongShortStrategy        : always in market, reverses on each crossover
  - optimize_and_validate()  : run grid optimisation on train data, evaluate on validation data
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from math import ceil
from pathlib import Path

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy

ROOT = Path(__file__).parent
BACKTEST_CACHE_DIR = ROOT / "cache" / "backtest"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def candles_to_df(candles: list[dict]) -> pd.DataFrame:
    """Convert list[dict] OHLCV candles to a backtesting.py-compatible DataFrame."""
    rows = []
    for c in candles:
        dt = c["date"]
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        rows.append({
            "Open":   float(c["open"]),
            "High":   float(c["high"]),
            "Low":    float(c["low"]),
            "Close":  float(c["close"]),
            "Volume": float(c["volume"]) if c.get("volume") is not None else 0.0,
        })
    index = pd.DatetimeIndex(
        [c["date"] if not isinstance(c["date"], str) else datetime.fromisoformat(c["date"])
         for c in candles],
        tz="UTC",
    )
    df = pd.DataFrame(rows, index=index)
    df.index.name = "Date"
    return df


def _compute_indicator(data_close: np.ndarray, ind_type: str, period: int) -> np.ndarray:
    """Compute SMA or EMA over a numpy array of close prices."""
    s = pd.Series(data_close)
    if ind_type == "sma":
        return s.rolling(period).mean().to_numpy()
    if ind_type == "ema":
        return s.ewm(span=period, adjust=False).mean().to_numpy()
    raise ValueError(f"Unknown indicator type: {ind_type}")


# ---------------------------------------------------------------------------
# Strategy classes
# ---------------------------------------------------------------------------

class LongCashStrategy(Strategy):
    """Go long when ind1 crosses above ind2; exit when ind1 crosses below ind2."""
    ind1_type: str = "price"
    ind2_type: str = "sma"
    ind1_period: int = 20
    ind2_period: int = 50

    def init(self) -> None:
        close = self.data.Close

        if self.ind1_type == "price":
            self._ind1 = self.I(lambda c: c, close, name="Ind1(Price)")
        else:
            p1 = self.ind1_period
            self._ind1 = self.I(_compute_indicator, close, self.ind1_type, p1, name=f"Ind1({self.ind1_type},{p1})")

        p2 = self.ind2_period
        self._ind2 = self.I(_compute_indicator, close, self.ind2_type, p2, name=f"Ind2({self.ind2_type},{p2})")

        self._entry_bar: int = -2  # bar index of last entry; -2 = never

    def next(self) -> None:
        ind1 = self._ind1[-1]
        ind2 = self._ind2[-1]
        ind1_prev = self._ind1[-2] if len(self._ind1) >= 2 else ind1
        ind2_prev = self._ind2[-2] if len(self._ind2) >= 2 else ind2

        if any(math.isnan(v) for v in (ind1, ind2, ind1_prev, ind2_prev)):
            return

        current_bar = len(self.data) - 1
        bars_held = current_bar - self._entry_bar

        if self.position.is_long:
            # Exit: downward crossover after holding ≥ 1 bar
            if bars_held >= 1 and ind1_prev >= ind2_prev and ind1 < ind2:
                self.position.close()
        else:
            # Entry: upward crossover, min 1 bar since last entry
            if bars_held >= 1 and ind1_prev <= ind2_prev and ind1 > ind2:
                self.buy(size=0.99)
                self._entry_bar = current_bar


class ShortCashStrategy(Strategy):
    """Go short when ind1 crosses below ind2; exit when ind1 crosses above ind2."""
    ind1_type: str = "price"
    ind2_type: str = "sma"
    ind1_period: int = 20
    ind2_period: int = 50

    def init(self) -> None:
        close = self.data.Close

        if self.ind1_type == "price":
            self._ind1 = self.I(lambda c: c, close, name="Ind1(Price)")
        else:
            p1 = self.ind1_period
            self._ind1 = self.I(_compute_indicator, close, self.ind1_type, p1, name=f"Ind1({self.ind1_type},{p1})")

        p2 = self.ind2_period
        self._ind2 = self.I(_compute_indicator, close, self.ind2_type, p2, name=f"Ind2({self.ind2_type},{p2})")

        self._entry_bar: int = -2

    def next(self) -> None:
        ind1 = self._ind1[-1]
        ind2 = self._ind2[-1]
        ind1_prev = self._ind1[-2] if len(self._ind1) >= 2 else ind1
        ind2_prev = self._ind2[-2] if len(self._ind2) >= 2 else ind2

        if any(math.isnan(v) for v in (ind1, ind2, ind1_prev, ind2_prev)):
            return

        current_bar = len(self.data) - 1
        bars_held = current_bar - self._entry_bar

        if self.position.is_short:
            # Exit: upward crossover after holding ≥ 1 bar
            if bars_held >= 1 and ind1_prev <= ind2_prev and ind1 > ind2:
                self.position.close()
        else:
            # Entry: downward crossover, min 1 bar since last entry
            if bars_held >= 1 and ind1_prev >= ind2_prev and ind1 < ind2:
                self.sell(size=0.99)
                self._entry_bar = current_bar


class LongShortStrategy(Strategy):
    """Always in market: long when ind1 > ind2, short when ind1 < ind2. Reverses on crossovers."""
    ind1_type: str = "price"
    ind2_type: str = "sma"
    ind1_period: int = 20
    ind2_period: int = 50

    def init(self) -> None:
        close = self.data.Close

        if self.ind1_type == "price":
            self._ind1 = self.I(lambda c: c, close, name="Ind1(Price)")
        else:
            p1 = self.ind1_period
            self._ind1 = self.I(_compute_indicator, close, self.ind1_type, p1, name=f"Ind1({self.ind1_type},{p1})")

        p2 = self.ind2_period
        self._ind2 = self.I(_compute_indicator, close, self.ind2_type, p2, name=f"Ind2({self.ind2_type},{p2})")

        self._entry_bar: int = -2

    def next(self) -> None:
        ind1 = self._ind1[-1]
        ind2 = self._ind2[-1]
        ind1_prev = self._ind1[-2] if len(self._ind1) >= 2 else ind1
        ind2_prev = self._ind2[-2] if len(self._ind2) >= 2 else ind2

        if any(math.isnan(v) for v in (ind1, ind2, ind1_prev, ind2_prev)):
            return

        current_bar = len(self.data) - 1
        bars_held = current_bar - self._entry_bar

        upward = ind1_prev <= ind2_prev and ind1 > ind2
        downward = ind1_prev >= ind2_prev and ind1 < ind2

        if self.position.is_long and bars_held >= 1 and downward:
            self.position.close()
            self.sell(size=0.99)
            self._entry_bar = current_bar
        elif self.position.is_short and bars_held >= 1 and upward:
            self.position.close()
            self.buy(size=0.99)
            self._entry_bar = current_bar
        elif not self.position:
            if upward:
                self.buy(size=0.99)
                self._entry_bar = current_bar
            elif downward:
                self.sell(size=0.99)
                self._entry_bar = current_bar


# ---------------------------------------------------------------------------
# Strategy factory
# ---------------------------------------------------------------------------

_STRATEGY_MAP: dict[str, type[Strategy]] = {
    "long_cash":  LongCashStrategy,
    "short_cash": ShortCashStrategy,
    "long_short": LongShortStrategy,
}


def _strategy_class(exposure: str) -> type[Strategy]:
    cls = _STRATEGY_MAP.get(exposure)
    if cls is None:
        raise ValueError(f"Unknown exposure: {exposure!r}. Choose from: {list(_STRATEGY_MAP)}")
    return cls


# ---------------------------------------------------------------------------
# Optimise + validate
# ---------------------------------------------------------------------------

def _build_optimize_kwargs(
    ind1_type: str,
    ind2_type: str,
    ind1_min: int,
    ind1_max: int,
    ind2_min: int,
    ind2_max: int,
    max_combos: int = 10_000,
) -> dict:
    """Build the kwargs dict for Backtest.optimize(), stepping ranges if needed."""
    kwargs: dict = {
        "ind1_type": [ind1_type],
        "ind2_type": [ind2_type],
    }

    if ind1_type != "price":
        r1_size = ind1_max - ind1_min + 1
        r2_size = ind2_max - ind2_min + 1
        total = r1_size * r2_size
        if total > max_combos:
            step = ceil(total ** 0.5 / (max_combos ** 0.5))
            step = max(step, 1)
        else:
            step = 1
        kwargs["ind1_period"] = range(ind1_min, ind1_max + 1, step)
        kwargs["ind2_period"] = range(ind2_min, ind2_max + 1, step)
    else:
        r2_size = ind2_max - ind2_min + 1
        total = r2_size
        if total > max_combos:
            step = ceil(r2_size / max_combos)
        else:
            step = 1
        kwargs["ind1_period"] = [1]  # ignored by strategy when ind1_type == "price"
        kwargs["ind2_period"] = range(ind2_min, ind2_max + 1, step)

    return kwargs


def _trades_to_list(stats: object, price_scale: float = 1.0) -> list[dict]:
    """Extract trade list from backtesting.py stats object."""
    trades_df = getattr(stats, "_trades", None)
    if trades_df is None or (hasattr(trades_df, "empty") and trades_df.empty):
        return []
    result = []
    for _, row in trades_df.iterrows():
        entry_d = row.get("EntryTime")
        exit_d  = row.get("ExitTime")
        size    = row.get("Size", 0)
        pnl     = row.get("PnL", None)
        result.append({
            "entry_date":  str(entry_d)[:10] if entry_d is not None else None,
            "exit_date":   str(exit_d)[:10]  if exit_d  is not None else None,
            "entry_price": float(row.get("EntryPrice", 0)) * price_scale,
            "exit_price":  float(row.get("ExitPrice", 0)) * price_scale if row.get("ExitPrice") is not None else None,
            "pnl":         float(pnl) if pnl is not None else None,
            "direction":   "Long" if size > 0 else "Short",
        })
    return result


def _open_position(val_stats: object, price_scale: float = 1.0) -> dict | None:
    """Return the open position (if any) at the end of the validation run with theoretical P&L."""
    try:
        strat = val_stats._strategy
        open_trades = strat.trades  # tuple of open Trade objects
        if not open_trades:
            return None
        trade = open_trades[0]  # strategy holds at most one position
        last_price = float(strat.data.Close[-1])
        entry_price = float(trade.entry_price)
        size = float(trade.size)
        entry_date = str(trade.entry_time)[:10]
        return {
            "entry_date":      entry_date,
            "entry_price":     entry_price * price_scale,
            "current_price":   last_price * price_scale,
            "theoretical_pnl": round(float(trade.pl), 2),
            "direction":       "Long" if size > 0 else "Short",
        }
    except Exception:  # noqa: BLE001
        return None


def _stats_summary(stats: object) -> dict:
    """Extract a concise P&L summary from backtesting.py stats."""
    trades = _trades_to_list(stats)
    closed = [t for t in trades if t["pnl"] is not None]
    net_pnl = sum(t["pnl"] for t in closed)
    wins = sum(1 for t in closed if t["pnl"] > 0)
    win_rate = (wins / len(closed) * 100) if closed else 0.0
    return {
        "num_trades":  len(closed),
        "net_pnl":     round(net_pnl, 2),
        "win_rate":    round(win_rate, 1),
    }


def optimize_and_validate(
    candles: list[dict],
    ind1_type: str,
    ind2_type: str,
    ind1_min: int,
    ind1_max: int,
    ind2_min: int,
    ind2_max: int,
    exposure: str,
    train_start: str,
    train_end: str,
    val_start: str,
) -> dict:
    """
    Run grid optimisation on training data, then evaluate best params on validation data.

    Returns a dict with keys:
      best_params, train_stats (with date_from/date_to), val_stats, val_trades
    """
    df = candles_to_df(candles)

    # Ensure tz-aware timestamps for comparison
    train_start_ts = pd.Timestamp(train_start, tz="UTC")
    train_end_ts   = pd.Timestamp(train_end,   tz="UTC")
    val_start_ts   = pd.Timestamp(val_start,   tz="UTC")

    # Use the newer of the requested train_start and the oldest available candle
    effective_train_start = max(train_start_ts, df.index[0])

    df_train = df[(df.index >= effective_train_start) & (df.index <= train_end_ts)]
    df_val   = df[df.index >= val_start_ts]

    if df_train.empty:
        raise ValueError(f"No training data before {train_end}")
    if df_val.empty:
        raise ValueError(f"No validation data after {val_start}")

    # Normalize all prices so the first training candle close = 1.0.
    # This ensures $1 000 cash is always sufficient regardless of asset price (e.g. BTC at $80k).
    # price_scale is used to convert normalized prices back to real dollars for display.
    price_scale = float(df_train["Close"].iloc[0])
    df_train = df_train.copy()
    df_val   = df_val.copy()
    for col in ("Open", "High", "Low", "Close"):
        df_train[col] = df_train[col] / price_scale
        df_val[col]   = df_val[col]   / price_scale

    cls = _strategy_class(exposure)
    opt_kwargs = _build_optimize_kwargs(ind1_type, ind2_type, ind1_min, ind1_max, ind2_min, ind2_max)

    # ---- Optimise on training data ----
    bt_train = Backtest(df_train, cls, commission=0, cash=1_000, exclusive_orders=True)
    train_stats = bt_train.optimize(
        **opt_kwargs,
        maximize="Equity Final [$]",
        return_heatmap=False,
    )

    # Extract best parameters from optimised strategy instance
    best_strat = train_stats._strategy
    best_ind1_period = getattr(best_strat, "ind1_period", 1)
    best_ind2_period = getattr(best_strat, "ind2_period", 20)
    best_ind1_type   = getattr(best_strat, "ind1_type", ind1_type)
    best_ind2_type   = getattr(best_strat, "ind2_type", ind2_type)

    best_params = {
        "ind1_type":   best_ind1_type,
        "ind2_type":   best_ind2_type,
        "ind1_period": int(best_ind1_period) if ind1_type != "price" else None,
        "ind2_period": int(best_ind2_period),
    }

    train_summary = _stats_summary(train_stats)
    train_summary["date_from"] = str(df_train.index[0])[:10]
    train_summary["date_to"]   = str(df_train.index[-1])[:10]

    # ---- Validate with best params ----
    bt_val = Backtest(df_val, cls, commission=0, cash=1_000, exclusive_orders=True)
    val_stats = bt_val.run(
        ind1_type=best_ind1_type,
        ind2_type=best_ind2_type,
        ind1_period=best_ind1_period,
        ind2_period=best_ind2_period,
    )

    val_summary = _stats_summary(val_stats)
    val_summary["date_from"] = str(df_val.index[0])[:10]
    val_summary["date_to"]   = str(df_val.index[-1])[:10]
    val_trades = _trades_to_list(val_stats, price_scale)
    open_pos   = _open_position(val_stats, price_scale)

    return {
        "best_params":   best_params,
        "train_stats":   train_summary,
        "val_stats":     val_summary,
        "val_trades":    val_trades,
        "open_position": open_pos,
    }


# ---------------------------------------------------------------------------
# Disk cache helpers
# ---------------------------------------------------------------------------

def _cache_key(
    symbol: str,
    ind1_type: str,
    ind2_type: str,
    ind1_min: int,
    ind1_max: int,
    ind2_min: int,
    ind2_max: int,
    exposure: str,
    train_start: str,
    train_end: str,
    val_start: str,
) -> str:
    raw = f"{symbol}_{ind1_type}_{ind1_min}-{ind1_max}_{ind2_type}_{ind2_min}-{ind2_max}_{exposure}_{train_start}_{train_end}_{val_start}"
    # Use a short hash to keep filenames manageable
    h = hashlib.sha1(raw.encode()).hexdigest()[:12]
    return f"{symbol.upper()}_{ind1_type}_{ind2_type}_{exposure}_{h}"


def cache_path(symbol: str, **kwargs) -> Path:
    key = _cache_key(symbol, **kwargs)
    return BACKTEST_CACHE_DIR / f"{key}.json"


def load_cache(symbol: str, **kwargs) -> dict | None:
    p = cache_path(symbol, **kwargs)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None


def save_cache(symbol: str, data: dict, **kwargs) -> None:
    BACKTEST_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = cache_path(symbol, **kwargs)
    p.write_text(json.dumps(data))


def delete_cache(symbol: str, **kwargs) -> bool:
    p = cache_path(symbol, **kwargs)
    if p.exists():
        p.unlink()
        return True
    return False
