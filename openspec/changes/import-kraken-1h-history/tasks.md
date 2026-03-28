## 1. Database Migration

- [x] 1.1 Create `031_kraken_historical_source.sql` registering `data_source_id = 5`, `name = 'Kraken Historical'`, `short_name = 'kraken_hist'`, `retrieval_priority = NULL`
- [x] 1.2 Run `migrate` CLI to apply migration on the target database

## 2. Kraken Pair Mapping Config

- [x] 2.1 Create `src/market_data/config/kraken_pairs.yaml` with known exceptions (e.g. `bitcoin: XBTUSD`)
- [x] 2.2 Implement `resolve_kraken_pair(instrument_id, ticker)` helper that reads the YAML and falls back to `{ticker.upper()}USD`

## 3. Import Script (CLI)

- [x] 3.1 Create `src/market_data/scripts/import_kraken_1h.py` with `main()` entry point
- [x] 3.2 Implement CSV parsing: headerless, columns `unix_ts, open, high, low, close, volume, trade_count`
- [x] 3.3 Implement batch upsert into `ohlcv` (`interval='1h'`, `source='kraken'`, `is_aggregated=FALSE`, `tick_1h = unix_ts / 3600`)
- [x] 3.4 Implement `_upsert_data_available()` call after successful import (`has_1h=True`, `data_source_id=5`)
- [x] 3.5 Register `import-kraken-1h` entry point in `pyproject.toml`
- [x] 3.6 Verify idempotency: running twice on same file produces no duplicate rows

## 4. REST API Endpoints

- [x] 4.1 Create `src/market_data/api/rest/kraken_import.py` with `router = APIRouter()`
- [x] 4.2 Implement `GET /v1/instruments/{symbol}/kraken-1h-status` — resolve symbol, resolve pair, check file existence, count gap rows, return JSON response
- [x] 4.3 Implement `POST /v1/instruments/{symbol}/import-kraken-1h` — validate file present, run import, return upsert summary; return HTTP 400 if no file
- [x] 4.4 Register the new router in the main FastAPI app
- [x] 4.5 Verify HTTP 404 returned for unknown symbols on both endpoints

## 5. ShortDesk — Backend Relay

- [x] 5.1 Add `_fetch_kraken_status(symbol)` helper in `web.py` that calls `GET /v1/instruments/{symbol}/kraken-1h-status`; returns `None` on error
- [x] 5.2 Call `_fetch_kraken_status` inside `asset_detail()` and pass `kraken_status` to the template context
- [x] 5.3 Add `POST /asset/{symbol}/import-kraken-1h` endpoint in `web.py` that relays to the platform and returns the JSON result

## 6. ShortDesk — UI

- [x] 6.1 Add "Kraken 1h" status card to the Fundamentals `div.row.g-3` in `asset_detail.html`: warning badge for no-file, info badge for gap, success badge for imported
- [x] 6.2 Add "Import Kraken 1h" button in the Strategy Controls section (alongside "Find Best SMA"); include HTMX `hx-post`, spinner, and `hx-swap` to update the badge
- [x] 6.3 Hide the import button when `has_file: false` or `already_imported: true`
- [x] 6.4 Show inline error message near the button when POST returns non-200

## 7. Verification

- [x] 7.1 Run `import-kraken-1h --symbol ADA` with the `ADAUSD_60.csv` file and confirm rows appear in `ohlcv` with `source = 'kraken'`
- [x] 7.2 Confirm `GET /v1/instruments/ada/kraken-1h-status` returns `already_imported: true` after import
- [ ] 7.3 Confirm the ShortDesk Fundamentals badge updates to "Kraken 1h ✓" after clicking the button
- [ ] 7.4 Confirm the import button disappears after a successful import
- [x] 7.5 Add an asset with no Kraken file and confirm the "No file: XYZUSD_60.csv" warning badge appears
