## Why

`BTN_UPDATE_OHLCV` is currently a stub that only logs to the browser console. Operators need a real import flow that reads locally-cached provider data files and ingests them into the OHLCV tables. Additionally, the instrument list opens to an empty selection on every load, forcing a manual click before any detail is visible; auto-selecting Bitcoin (BTC) on startup removes that extra step.

## What Changes

- On page load, automatically select the first Bitcoin (`BTC`) entry in the instrument list so fundamentals and OHLCV sections are populated immediately
- Replace the `BTN_UPDATE_OHLCV` stub with a real import flow:
  - Determine the best data source for the selected interval by consulting the `ohlcv_data_available` table (prefer source with `has_<interval> = true` and highest `retrieval_priority`)
  - Derive the expected local cache path: `/appdata/<source_short_name>/<data_class>/<interval_label>` (e.g. `/appdata/eodhd/intraday_historical_data/1-hour`)
  - Call a new backend endpoint `POST /v1/admin/import-ohlcv-cache` with `instrument_id`, `interval`, and `data_source_id`; the backend checks the folder, imports all files found, upserts into `ohlcv`, and returns a summary
  - On success: show count of imported rows in the fundamentals pane and refresh the OHLCV availability sections
  - On folder-not-found (new `404`-style error code from backend): show an inline error message with the exact expected folder path
- Add a new admin API endpoint `POST /v1/admin/import-ohlcv-cache` that encapsulates the folder-check → parse → upsert → migration pipeline

## Capabilities

### New Capabilities

- `ohlcv-cache-importer`: Backend service that, given `(instrument_id, interval, data_source_id)`, resolves the cache folder path, scans and parses data files (CSV/JSON), upserts rows into `ohlcv`, and returns a structured result including row count and any errors. Returns a distinct error payload when the expected folder does not exist.

### Modified Capabilities

- `management-console`: Auto-select Bitcoin on startup; replace `BTN_UPDATE_OHLCV` stub with real cache-import API call and inline result/error display

## Impact

- **Console UI** (`src/market_data/api/rest/console.py`): JS changes to `loadInstruments` (auto-select BTC after load) and `btnOhlcv` click handler (call new endpoint, render result/error)
- **REST API** (`src/market_data/api/rest/`): New router or extension of admin router with `POST /v1/admin/import-ohlcv-cache`
- **Ingestion** (`src/market_data/ingestion/`): New module or function for file-based OHLCV import from the `/appdata` folder tree
- **DB**: No schema changes; uses existing `ohlcv`, `data_source`, and `ohlcv_data_available` tables
