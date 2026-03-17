## 1. Database Migration

- [x] 1.1 Create `src/market_data/db/migrations/017_trading_strategies.sql` with the `trading_strategies` table definition (PK: `instrument_id, strategy_name, indicator_name`)
- [x] 1.2 Verify `uv run migrate` applies the migration cleanly on a fresh database and is skipped on re-run

## 2. Strategy Engine

- [x] 2.1 Create `src/market_data/strategies/__init__.py`
- [x] 2.2 Create `src/market_data/strategies/backtest.py` — port `sma`, `backtest_short_strategy`, `backtest_long_strategy` verbatim from `ShortDesk/draw_chart.py`
- [x] 2.3 Create `src/market_data/strategies/best_sma.py` — implement `compute_best_sma(instrument_id, parameters)` reading OHLCV from DuckDB, raising `ValueError` if no `1d` rows found, running the grid search over [3, 50] × [3, 50] on the training slice (first 80 %), returning `{"sma_low": int, "sma_high": int}`
- [x] 2.4 Create `src/market_data/strategies/registry.py` — define `STRATEGY_REGISTRY = {"best_sma": compute_best_sma}`

## 3. CLI

- [x] 3.1 Create `src/market_data/cli/compute_indicators.py` — implement argument parsing (`--strategy`, `--symbol`, `--sl-short`, `--sl-long`, `--pos-usd`), per-instrument loop with error catching, UPSERT of results into `trading_strategies`, stdout progress lines, exit code 0/1
- [x] 3.2 Register `compute-indicators` script entry point in `pyproject.toml` pointing to `market_data.cli.compute_indicators:main`
- [x] 3.3 Verify `uv run compute-indicators --strategy best_sma --symbol BTC` runs end-to-end and writes rows to the database

## 4. REST API

- [x] 4.1 Create `src/market_data/api/rest/trading_strategies.py` — implement `GET /v1/trading-strategies/{symbol}` (with optional `strategy_name` filter, 404 if no rows) and `POST /v1/trading-strategies/{symbol}/compute` (validates strategy name, errors on missing OHLCV, stores results)
- [x] 4.2 Register the new router in `src/market_data/api/rest/app.py`
- [x] 4.3 Verify `GET /v1/trading-strategies/BTC` returns 404 before compute and 200 after

## 5. ShortDesk Integration

- [x] 5.1 Add `MARKET_DATA_PLATFORM_URL` config (env var with default `http://localhost:8010`) to `ShortDesk/web.py`
- [x] 5.2 Replace the inline `_find_best_sma` call in `best_sma_endpoint` with an `httpx.get` to `GET /v1/trading-strategies/{symbol}?strategy_name=best_sma`; extract `sma_low` and `sma_high` from the response
- [x] 5.3 Return HTTP 422 with error when the platform returns 404
- [x] 5.4 Keep the existing OOS validation logic (runs locally using the returned sma_low / sma_high values)

## 6. Tests

- [x] 6.1 Add unit tests for `sma`, `backtest_short_strategy`, `backtest_long_strategy` in `tests/test_strategies.py`
- [x] 6.2 Add unit test for `compute_best_sma` with a minimal fixture candle set
- [x] 6.3 Add integration tests for `GET /v1/trading-strategies/{symbol}` and `POST /v1/trading-strategies/{symbol}/compute` in `tests/test_api_rest.py`
- [x] 6.4 Add CLI smoke test (subprocess call) verifying correct exit codes for success and unknown-strategy error cases

## 7. Documentation

- [x] 7.1 Add `trading_strategies` table to `docs/schema.md` (schema, PK, description of columns)
- [x] 7.2 Add `compute-indicators` CLI usage section to `README.md`
