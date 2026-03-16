## MODIFIED Requirements

### Requirement: best_sma strategy
The module SHALL provide `compute_best_sma(instrument_id, parameters)` that:
1. Aggregates `1h` OHLCV candles for `instrument_id` from DuckDB into daily bars using a SQL CTE grouped by UTC calendar day (`DATE_TRUNC('day', ts)`). Within each day: `open` = value at `MIN(ts)`, `high` = `MAX(high)`, `low` = `MIN(low)`, `close` = value at `MAX(ts)`, `volume` = `SUM(volume)`. Rows are ordered ascending by day.
2. Raises a `ValueError` if no `1h` rows are found for the instrument.
3. Uses the first 80% of aggregated daily bars as the training slice.
4. Pre-computes SMA arrays for all periods in [3, 50] on the LOW and HIGH price series of the training slice.
5. Iterates all (sma_low_period, sma_high_period) combinations in [3, 50] × [3, 50], runs both backtests, scores by combined average P&L per closed trade (total combined P&L / total closed trade count; −∞ if no closed trades).
6. Returns a dict `{"sma_low": <int>, "sma_high": <int>}`.

#### Scenario: Normal computation succeeds from 1h data
- **WHEN** `compute_best_sma` is called for an instrument with sufficient `1h` candles in `ohlcv`
- **THEN** it returns a dict with `sma_low` and `sma_high` keys, both integers in [3, 50]

#### Scenario: No 1h OHLCV data raises error
- **WHEN** `compute_best_sma` is called for an instrument that has no rows in the `ohlcv` table with `interval='1h'`
- **THEN** a `ValueError` (or subclass) is raised with a message indicating OHLCV data is absent
