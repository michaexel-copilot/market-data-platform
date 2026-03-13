## Why

The management console currently has no way to trigger data source migrations from the UI, and fundamental data lacks a formal tracking layer showing which source provides each attribute and when it was last updated. Adding a `data_source` registry table and an `attribute_source_map` table, together with a "Migrate Fundamental Data" action and per-instrument fundamentals detail view, closes this gap and makes the provenance of every data field visible and actionable.

## What Changes

- Add two new database tables: `data_source` (registry of known data providers) and `attribute_source_map` (per-attribute provenance + last-updated tracking)
- Add a ticker-disambiguation mapping table `ticker_source_map` to resolve ambiguous ticker symbols across providers (e.g. CoinMarketCap vs Hyperliquid)
- Add an **Action Button List** to the top bar of the management console, right-aligned as a sibling of `#SEG_ASSET_CLASS`, containing a "Migrate Fundamental Data" button (`BTN_MIGRATE_FUNDAMENTALS`)
- Wire `BTN_MIGRATE_FUNDAMENTALS` to a new backend endpoint `POST /v1/admin/migrate-fundamentals` that performs the migration and refreshes the instrument list
- When a ticker is clicked in the instrument list, display its fundamental data in the main pane (already partially wired; this change makes it functional end-to-end after migration)

## Capabilities

### New Capabilities

- `data-source-registry`: Registry of known data providers with name, short name, base URL, API page URL, and retrieval priority

### Modified Capabilities

- `management-console`: Add right-aligned action button list to top bar with `BTN_MIGRATE_FUNDAMENTALS`; wire instrument-click to show fundamentals in main pane
- `instrument-registry`: Add `attribute_source_map` and `ticker_source_map` tables to track per-attribute provenance and disambiguate cross-source tickers

## Impact

- **DB migrations** (`src/market_data/db/migrations/`): new SQL migrations for `data_source`, `attribute_source_map`, `ticker_source_map`
- **REST API** (`src/market_data/api/rest/`): new `POST /v1/admin/migrate-fundamentals` endpoint
- **Management console** (`src/market_data/api/rest/console.py`): HTML/JS changes for the action button list and fundamentals-on-click
- **Ingestion layer** (`src/market_data/ingestion/`): migration logic to populate `attribute_source_map` and `ticker_source_map` from existing CoinMarketCap static data
- No changes to gRPC or JSON-RPC contracts
