## Why

`uv run compute-indicators --strategy best_sma` always errors because the `ohlcv` table is empty: there is no CLI to bulk-import hourly data from the `eodhd` cache into the database. Additionally, `compute_best_sma` queries `interval='1d'` candles but only hourly (`1h`) data exists in `/appdata/eodhd/intraday_historical_data/1-hour/`. Finally, `ShortDesk/web.py` bypasses the database entirely with a local JSON file cache, violating the single-source-of-truth principle.

## What Changes

- **New**: `import-ohlcv` CLI (`uv run import-ohlcv --interval 1h [--symbol TICKER]`) — iterates all active instruments and calls the eodhd cache importer for each.
- **New**: `POST /v1/admin/import-ohlcv` REST endpoint — performs the bulk import server-side, returns `{ok, errors, results}` mirroring the compute-indicators endpoint pattern.
- **Changed**: `compute_best_sma` — replace `SELECT … WHERE interval='1d'` with a SQL aggregation of `1h` candles to daily OHLCV (open=first, high=max, low=min, close=last, volume=sum grouped by UTC day).
- **Changed**: `ShortDesk/web.py` `best_sma_endpoint` — remove `_BEST_SMA_CACHE` (in-memory), `_BEST_SMA_CACHE_DIR` (JSON files), `_load_best_sma_cache`, `_save_best_sma_cache`, and `_find_best_sma`. The endpoint reads exclusively from the market-data-platform API; returns HTTP 503 if no precomputed data is available yet.

## Capabilities

### New Capabilities

- `import-ohlcv-cli`: New `import-ohlcv` CLI entry point and corresponding `POST /v1/admin/import-ohlcv` REST endpoint for bulk-importing OHLCV data for all active instruments from the local eodhd cache.

### Modified Capabilities

- `strategy-engine`: Requirement change — `compute_best_sma` SHALL aggregate `1h` candles to daily OHLCV via SQL (not read `interval='1d'` rows directly), since only hourly data is available in the database.

## Impact

- `market-data-platform`:
  - New file: `src/market_data/cli/import_ohlcv.py`
  - Modified: `src/market_data/api/rest/admin.py` (new `/v1/admin/import-ohlcv` endpoint)
  - Modified: `src/market_data/strategies/best_sma.py` (SQL aggregation instead of direct `1d` query)
  - Modified: `pyproject.toml` (register `import-ohlcv` script entry point)
- `ShortDesk`:
  - Modified: `web.py` (remove local best_sma cache and fallback computation)
