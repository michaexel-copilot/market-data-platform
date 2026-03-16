"""best_sma strategy — brute-force grid search for optimal SMA period pair."""
from __future__ import annotations

from market_data.db.connection import get_connection
from market_data.strategies.backtest import sma, backtest_short_strategy, backtest_long_strategy

_SMA_MIN = 3
_SMA_MAX = 50


def compute_best_sma(instrument_id: str, parameters: dict | None = None) -> dict[str, int]:
    """Find the (sma_low, sma_high) period pair that maximises combined average
    P&L per closed trade, using the first 80 % of daily candles as the training slice.

    Args:
        instrument_id: UUID from the instruments table.
        parameters: Optional dict with keys sl_short (%), sl_long (%), pos_usd ($).

    Returns:
        {"sma_low": int, "sma_high": int}

    Raises:
        ValueError: If no daily OHLCV rows exist for the instrument.
    """
    params = parameters or {}
    sl_short = float(params.get("sl_short", 10)) / 100.0
    sl_long = float(params.get("sl_long", 10)) / 100.0
    pos_usd = float(params.get("pos_usd", 100))

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
            WHERE instrument_id = ? AND interval = '1h'
            GROUP BY DATE_TRUNC('day', ts)
        )
        SELECT
            d.day,
            o_open.open,
            d.high,
            d.low,
            o_close.close
        FROM daily d
        JOIN ohlcv o_open  ON o_open.instrument_id  = ?
                          AND o_open.interval        = '1h'
                          AND o_open.ts              = d.first_ts
        JOIN ohlcv o_close ON o_close.instrument_id = ?
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

    candles = [
        {"date": str(r[0])[:10], "open": r[1], "high": r[2], "low": r[3], "close": r[4]}
        for r in rows
    ]

    split_idx = max(1, int(len(candles) * 0.8))
    train = candles[:split_idx]

    lows   = [c["low"]   for c in train]
    highs  = [c["high"]  for c in train]

    sma_low_arrays  = {p: sma(lows,  p) for p in range(_SMA_MIN, _SMA_MAX + 1)}
    sma_high_arrays = {p: sma(highs, p) for p in range(_SMA_MIN, _SMA_MAX + 1)}

    best_score = float("-inf")
    best_pair = (_SMA_MIN, _SMA_MIN)

    for sma_low_p in range(_SMA_MIN, _SMA_MAX + 1):
        short_trades = backtest_short_strategy(
            train, sma_low_arrays[sma_low_p],
            position_size_usd=pos_usd,
            stop_loss_pct=sl_short,
        )
        for sma_high_p in range(_SMA_MIN, _SMA_MAX + 1):
            long_trades = backtest_long_strategy(
                train, sma_high_arrays[sma_high_p],
                position_size_usd=pos_usd,
                stop_loss_pct=sl_long,
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
