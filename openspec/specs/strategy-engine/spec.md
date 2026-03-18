# Strategy Engine

## Purpose

Defines the pure-Python strategy computation module: the backtest primitives (`sma`, `backtest_short_strategy`, `backtest_long_strategy`) and the `best_sma` strategy that uses them to find optimal SMA period pairs.

## ADDED Requirements

### Requirement: SMA computation
The module SHALL provide a `sma(values, period)` function that returns a list of the same length as `values`, where the first `period - 1` entries are `None` and subsequent entries are the simple moving average over the preceding `period` values.

#### Scenario: Normal computation
- **WHEN** `sma([1.0, 2.0, 3.0, 4.0, 5.0], 3)` is called
- **THEN** the result is `[None, None, 2.0, 3.0, 4.0]`

#### Scenario: Period equals 1
- **WHEN** `sma(values, 1)` is called
- **THEN** every entry is returned unchanged (no None values)

---

### Requirement: Short strategy backtest
The module SHALL provide `backtest_short_strategy(candles, sma_low, position_size_usd, stop_loss_pct)` implementing the following rules on daily candle data:
- **Entry**: close crosses below `sma_low` (previous close ≥ previous SMA_LOW, current close < current SMA_LOW).
- **Stop-loss exit**: close ≥ entry_price × (1 + stop_loss_pct) → exit at stop price (loss).
- **Profit exit**: close ≥ current SMA_LOW AND current SMA_LOW < entry_price → exit at SMA_LOW (profit).
- No new position while one is open.
- Returns a list of trade dicts including `entry_date`, `entry_price`, `exit_date`, `exit_price`, `pnl`, `is_open`.

#### Scenario: Entry signal fires
- **WHEN** the previous candle's close was ≥ the previous SMA_LOW and the current candle's close is < the current SMA_LOW
- **THEN** a new trade is opened with `is_open=True` and `entry_price` equal to the current close

#### Scenario: Stop-loss triggers
- **WHEN** an open short position's current close ≥ entry_price × (1 + stop_loss_pct)
- **THEN** the trade is closed at the stop price with a negative `pnl`

#### Scenario: Profit exit triggers
- **WHEN** current SMA_LOW < entry_price and current close ≥ current SMA_LOW
- **THEN** the trade is closed at SMA_LOW with a positive `pnl`

#### Scenario: No double entry
- **WHEN** a short position is already open
- **THEN** no new entry signal is acted upon until the position is closed

---

### Requirement: Long strategy backtest
The module SHALL provide `backtest_long_strategy(candles, sma_high, position_size_usd, stop_loss_pct)` implementing the mirror of the short strategy:
- **Entry**: close crosses above `sma_high` (previous close ≤ previous SMA_HIGH, current close > current SMA_HIGH).
- **Stop-loss exit**: close ≤ entry_price × (1 - stop_loss_pct) → exit at stop price (loss).
- **Profit exit**: SMA_HIGH > entry_price AND close ≤ current SMA_HIGH → exit at SMA_HIGH (profit).
- No new position while one is open.

#### Scenario: Entry signal fires
- **WHEN** the previous candle's close was ≤ the previous SMA_HIGH and the current candle's close is > the current SMA_HIGH
- **THEN** a new long trade is opened with `is_open=True`

#### Scenario: Stop-loss triggers
- **WHEN** an open long position's current close ≤ entry_price × (1 - stop_loss_pct)
- **THEN** the trade is closed at the stop price with a negative `pnl`

---

### Requirement: best_sma strategy
The module SHALL provide `compute_best_sma(instrument_id, parameters)` that:
1. Aggregates `1h` OHLCV candles for `instrument_id` from PostgreSQL into daily bars using a SQL CTE grouped by UTC calendar day (`DATE_TRUNC('day', ts)`). Within each day: `open` = value at `MIN(ts)`, `high` = `MAX(high)`, `low` = `MIN(low)`, `close` = value at `MAX(ts)`, `volume` = `SUM(volume)`. Rows are ordered ascending by day.
2. Raises a `ValueError` if no `1h` rows are found for the instrument.
3. Uses the first 80% of aggregated daily bars as the training slice.
4. Pre-computes SMA arrays for all periods in [3, 50] on the LOW and HIGH price series of the training slice.
5. Iterates all (sma_low_period, sma_high_period) combinations in [3, 50] × [3, 50], runs both backtests, scores by combined average P&L per closed trade.
6. Returns a dict `{"sma_low": <int>, "sma_high": <int>}`.

All SQL parameters SHALL use `%s` placeholders (psycopg3 / DB-API 2.0 style). The function SHALL obtain a cursor from `get_connection()` and call `cursor.execute()` / `cursor.fetchall()`.

#### Scenario: Normal computation succeeds from 1h data
- **WHEN** `compute_best_sma` is called for an instrument with sufficient `1h` candles in `ohlcv`
- **THEN** it returns a dict with `sma_low` and `sma_high` keys, both integers in [3, 50]

#### Scenario: No 1h OHLCV data raises error
- **WHEN** `compute_best_sma` is called for an instrument that has no rows in the `ohlcv` table with `interval='1h'`
- **THEN** a `ValueError` (or subclass) is raised with a message indicating OHLCV data is absent

#### Scenario: Parameters passed through to backtests
- **WHEN** `compute_best_sma` is called with `parameters={"sl_short": 5, "sl_long": 8, "pos_usd": 200}`
- **THEN** the backtest functions receive `stop_loss_pct=0.05` and `0.08` respectively and `position_size_usd=200`

---

### Requirement: Strategy registry
The module SHALL expose a `STRATEGY_REGISTRY` dict mapping strategy name strings to callable strategy functions. The `best_sma` strategy SHALL be registered under the key `"best_sma"`.

#### Scenario: Registered strategy callable
- **WHEN** `STRATEGY_REGISTRY["best_sma"](instrument_id, parameters)` is called
- **THEN** it behaves identically to calling `compute_best_sma(instrument_id, parameters)` directly
