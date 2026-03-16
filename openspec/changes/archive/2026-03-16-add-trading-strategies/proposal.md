## Why

The best-SMA indicator computation currently lives inside `FindShortOpportunites/web.py` and runs on-demand per HTTP request, taking several seconds per instrument. Moving this logic — and the underlying backtest engine — into `market-data-platform` centralises all strategy computations, allows results to be precomputed and persisted, and provides a generic foundation for adding further indicators in the future.

## What Changes

- Add a `trading_strategies` table to the DuckDB database storing precomputed indicator values per instrument, strategy, and parameter set.
- Add a strategy engine module inside `market_data/strategies/` containing:
  - Pure backtest functions (`sma`, `backtest_short_strategy`, `backtest_long_strategy`) ported from `FindShortOpportunites/draw_chart.py`.
  - A `best_sma` strategy that brute-force searches SMA_LOW × SMA_HIGH ∈ [3, 50] using the first 80 % of OHLCV candles and stores the winning pair as indicator values.
- Add a database migration (`017_trading_strategies.sql`) creating the new table.
- Add REST endpoints under `/v1/trading-strategies/`:
  - `GET /v1/trading-strategies/{symbol}` — read precomputed indicators for an instrument (filtered optionally by `strategy_name`). Returns 404 with an actionable error message if no data has been computed yet.
  - `POST /v1/trading-strategies/{symbol}/compute` — trigger computation for a single instrument (for future UI use; implemented but not required by the CLI).
- Add a CLI entry point `compute-indicators` that batch-computes indicators for all active instruments (or a single symbol with `--symbol`) by reading OHLCV from DuckDB and writing results to `trading_strategies`. Exits with an error per instrument if OHLCV data is absent.
- Update `FindShortOpportunites/web.py`: the `GET /asset/{symbol}/best-sma` endpoint stops computing inline and instead reads from `market-data-platform`'s REST API. Returns an error to the caller if no precomputed data is available.

## Capabilities

### New Capabilities

- `trading-strategies-store`: Persistent storage of named indicator values (strategy name, indicator name, value, parameters, timestamp) per instrument in DuckDB.
- `strategy-engine`: Pure Python backtest functions and the `best_sma` strategy algorithm; usable by both the REST layer and the CLI without an HTTP round-trip.
- `compute-indicators-cli`: CLI command to bulk-compute and store indicator values for all or selected instruments, reading OHLCV from the database.
- `trading-strategies-api`: REST endpoints to query precomputed indicators and trigger single-instrument computation.

### Modified Capabilities

*(none — no existing spec-level requirements change)*

## Impact

- **market-data-platform**: new migration, new `market_data/strategies/` package, new REST router, new CLI entry point, `pyproject.toml` updated with new script.
- **FindShortOpportunites**: `web.py` `best_sma_endpoint` simplified — delegates to `market-data-platform` REST, removes inline `_find_best_sma` call; existing OOS cache behaviour unchanged (OOS results are still derived locally from the returned SMA values).
- **Dependencies**: no new external libraries required; `httpx` (already present in `FindShortOpportunites`) used for the outbound call.
- **Deployment**: `compute-indicators` must be run (manually or via cron) before the `FindShortOpportunites` UI can display best-SMA values for an instrument.
