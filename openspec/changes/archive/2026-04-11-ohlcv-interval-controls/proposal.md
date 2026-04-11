## Why

The OHLCV Time Range section in the management console shows per-interval first/last timestamps but offers no per-interval refresh control. The global "Update OHLCV Data" action bar button runs a full multi-step smart-update across all intervals with no granularity. Additionally, the `1m` row never appears unless the instrument already has 1m records — making it impossible to see at a glance that 1m ingestion has not been run yet.

## What Changes

- **Always include `1m` in the interval table**: The `ohlcv-availability` endpoint always returns a `1m` entry even when no records exist (`first` and `last` will be `null`, displayed as `—`).

- **Add `Actions` column to `ohlcv-range-table`**: The table grows a fourth rightmost column in both header and every data row.

- **Per-row "Update" button**: Each row's Actions cell contains an "Update" button that:
  - Is **hidden** when `auto_update` is `true` for that interval.
  - Is **disabled** when the last candle is fresh (not yet stale). Staleness thresholds:
    - `1m` — last candle timestamp < now − 1 min
    - `5m` — last candle timestamp < now − 5 min
    - `1h` — last candle timestamp < now − 1 h
    - `1d` — last candle date < today (UTC, i.e. after 00:00 UTC)
  - Is always **enabled** when `last` is `null` (no data ingested yet).
  - On click, calls `POST /v1/instruments/{instrument_id}/update-ohlcv/{interval}`. For `1m`, this fetches fresh candles from Binance. For derived intervals (`5m`, `1h`, `1d`), this runs aggregation from existing lower-resolution data only — no external fetch. The user is expected to update `1m` first if that data is stale.
  - On completion, refreshes the section via `_refreshOhlcvSections()`.

- **Per-row "Auto-update" checkbox**: Each row's Actions cell also contains a checkbox labelled "Auto" that:
  - On toggle, calls `PUT /v1/instruments/{instrument_id}/ohlcv-update-settings/{interval}` with `{ "auto_update": true/false }`.
  - When `auto_update` is `true`, the Update button is hidden for that row.
  - Checkbox state is loaded from `GET /v1/instruments/{instrument_id}/ohlcv-update-settings`, fetched in parallel with the three existing promises inside `loadFundamentals()`.

## New Backend Requirements

- **DB migration** — new table `ohlcv_update_settings`:
  - Columns: `instrument_id VARCHAR NOT NULL REFERENCES instruments(instrument_id)`, `interval VARCHAR NOT NULL`, `auto_update BOOLEAN NOT NULL DEFAULT FALSE`
  - Primary key: `(instrument_id, interval)`

- **New endpoints**:
  - `GET /v1/instruments/{instrument_id}/ohlcv-update-settings` — returns `{ "intervals": { "1m": { "auto_update": false }, … } }`
  - `PUT /v1/instruments/{instrument_id}/ohlcv-update-settings/{interval}` — upserts `auto_update` flag.
  - `POST /v1/instruments/{instrument_id}/update-ohlcv/{interval}` — for `1m`: Binance fetch; for `5m`/`1h`/`1d`: aggregation from existing records. Returns a summary message for console feedback.

## Capabilities

### New Capabilities
- `ohlcv-per-interval-update`: Manual Update button per interval row, staleness-gated, routes to fetch (1m) or aggregation (derived intervals).
- `ohlcv-auto-update-setting`: Per-instrument per-interval `auto_update` flag persisted in `ohlcv_update_settings`; when enabled, hides the manual Update button.

### Modified Capabilities
- `ohlcv-availability-1m-always-present`: The `ohlcv-availability` endpoint now always includes a `1m` key regardless of whether any 1m data has been ingested.

## Impact

- **`market-data-platform/src/market_data/api/rest/instruments.py`** — `ohlcv_availability`: always include `1m`; add `GET ohlcv-update-settings` handler.
- **`market-data-platform/src/market_data/api/rest/admin.py`** — `PUT ohlcv-update-settings/{interval}` and `POST update-ohlcv/{interval}` handlers.
- **`market-data-platform/src/market_data/db/migrations/`** — new migration for `ohlcv_update_settings`.
- **`market-data-platform/src/market_data/api/rest/console.py`** — `loadFundamentals()` and `_refreshOhlcvSections()`: fetch settings in parallel, render Actions column with staleness-gated Update button and Auto checkbox, wire click/change handlers.
