## Why

Crypto instruments in the database lack 1h OHLCV history prior to the point where
live ingestion began, leaving a multi-year gap between an asset's `launch_date` and
the earliest candle currently stored. Kraken publishes complete historical OHLCV
flat files (one CSV per pair) that cover this gap. Importing them closes the gap and
makes full-history backtesting meaningful.

## What Changes

- **New migration** (`031`) registers Kraken Historical as a data source (`data_source_id = 5`).
- **New YAML config** (`config/kraken_pairs.yaml`) maps canonical `instrument_id` →
  Kraken pair filename, applying the default `{TICKER}USD` convention for most assets
  and listing only the exceptions (e.g. `bitcoin → XBTUSD`).
- **New CLI script** `import-kraken-1h` reads a `{PAIR}_60.csv` file from a
  configurable data directory (`/mnt/ds420/data/kraken/1-hour`), upserts 1h rows into
  `ohlcv` for the matching canonical `instrument_id`, and updates
  `ohlcv_data_available`.
- **New REST endpoints** on the market-data-platform expose gap status and trigger
  on-demand import for a given symbol.
- **ShortDesk UI** gains a "Kraken 1h" status badge in the Fundamentals accordion
  (showing file-missing / gap size / imported state) and an "Import Kraken 1h" button
  in the Strategy Controls action bar.

## Capabilities

### New Capabilities

- `kraken-historical-importer`: CLI + REST API for importing Kraken historical 1h
  OHLCV flat files into the platform; includes Kraken-pair mapping config, gap
  detection query, and `ohlcv_data_available` bookkeeping.
- `kraken-1h-gap-status-ui`: ShortDesk UI affordances — Fundamentals badge showing
  file/gap/imported state, and action-bar button triggering the import via the
  platform REST API.

### Modified Capabilities

_(none — existing APIs and data flows are unchanged; new rows in `ohlcv` are
additive with `source = 'kraken'`)_

## Impact

- **market-data-platform**
  - New migration file `031_kraken_historical_source.sql`
  - New file `src/market_data/config/kraken_pairs.yaml`
  - New script `src/market_data/scripts/import_kraken_1h.py`
  - New entry point `import-kraken-1h` in `pyproject.toml`
  - New REST router `src/market_data/api/rest/kraken_import.py` (two endpoints)
  - No schema changes beyond migration 031
- **ShortDesk**
  - `web.py`: new helper to fetch kraken status; new POST relay endpoint
  - `templates/asset_detail.html`: new status card in Fundamentals; new action button
- **Infrastructure**: `/mnt/ds420/data/kraken/1-hour/` must be accessible from the
  market-data-platform process (confirmed ✓)
