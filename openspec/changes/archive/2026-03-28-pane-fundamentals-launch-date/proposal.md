## Why

The `PANE_FUNDAMENTALS` display in the management console lacks the asset launch date, even though the `instruments` table already has a `launch_date` column and CoinMarketCap's `cmc_map` table stores `first_historical_data` for each coin. Surfacing the launch date gives operators immediate context about asset age and history directly in the console.

## What Changes

- Populate `instruments.launch_date` from `cmc_map.first_historical_data` during the `migrate-fundamentals` enrichment step (crypto assets only).
- Extend `GET /v1/instruments/{symbol}/fundamentals` to include `launch_date` from the base `instruments` row in its response payload.
- Add a **Launch Date** row to the `PANE_FUNDAMENTALS` key-value table in the management console, displaying the value as `YYYY-MM-DD` (or a dash if null).

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `management-console`: `PANE_FUNDAMENTALS` requirement extended — the key-value table MUST display `launch_date` sourced from the fundamentals API response.
- `coinmarketcap-static-importer`: enrichment step MUST write `instruments.launch_date` from `cmc_map.first_historical_data` when migrating fundamentals for crypto instruments.

## Impact

- **`migrate_fundamentals.py`** — adds one `UPDATE` statement to set `launch_date` from `cmc_map`.
- **`src/market_data/api/rest/instruments.py`** — `get_fundamentals()` must join `instruments` to include `launch_date` in the response dict.
- **`src/market_data/api/rest/console.py`** — JS render function for `PANE_FUNDAMENTALS` must add the Launch Date row.
- **No schema migration needed** — `launch_date DATE` already exists on `instruments`.
- **No breaking API changes** — adding a field to the fundamentals response is additive.
