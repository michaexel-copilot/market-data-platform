## 1. Database Migration

- [x] 1.1 Create `src/market_data/db/migrations_pg/030_ohlcv_is_aggregated.sql` — `ALTER TABLE ohlcv ADD COLUMN IF NOT EXISTS is_aggregated BOOLEAN NOT NULL DEFAULT FALSE`
- [x] 1.2 Verify migration applies cleanly against the local database with `uv run migrate`
- [x] 1.3 Confirm all existing rows have `is_aggregated = FALSE` after migration

## 2. Data Model

- [x] 2.1 Add `is_aggregated: bool = False` field to `OHLCVRecord` in `src/market_data/models/ohlcv.py`

## 3. Writer — Aggregation-Aware Upsert

- [x] 3.1 Update the `ON CONFLICT DO UPDATE SET` clause in `write_ohlcv` (`src/market_data/ingestion/writer.py`) to add `is_aggregated` to the row tuple and column list
- [x] 3.2 Replace the flat `excluded.X` assignments with `CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE THEN excluded.X ELSE ohlcv.X END` guards for every mutable column (open, high, low, close, volume, vwap, trade_count, market_cap, source, ingested_at, tick_1h, tick_1d, is_aggregated)
- [x] 3.3 Verify real candle overwrites aggregated candle via unit test
- [x] 3.4 Verify aggregated candle does not overwrite real candle via unit test

## 4. Admin Endpoint — smart-update-ohlcv

- [x] 4.1 Add `SmartUpdateOhlcvRequest` Pydantic model to `src/market_data/api/rest/admin.py`
- [x] 4.2 Add `POST /v1/admin/smart-update-ohlcv` route handler
- [x] 4.3 Implement instrument existence check (HTTP 404 if not found)
- [x] 4.4 Implement 1h freshness check step (query `MAX(ts)` at `interval = '1h'`, 5-hour threshold)
- [x] 4.5 Implement conditional 1h ingest step (call `_run_interval_job(Interval.ONE_HOUR, instrument_id=…, fill_gaps=True)` when stale)
- [x] 4.6 Implement 1m gap detection step (query `MAX(ts)` at `interval = '1m'`, compute `gap_hours`)
- [x] 4.7 Implement Binance availability check step (query `ohlcv_data_available JOIN data_source`)
- [x] 4.8 Implement Binance 1m fetch step (`BinanceConnector.fetch_ohlcv` for gap range)
- [x] 4.9 Implement 1m→1h aggregation step (Python-side bucketing: open/high/low/close/volume, `source = "aggregated:binance_1m"`, `is_aggregated = True`)
- [x] 4.10 Persist aggregated 1h candles via `write_ohlcv`
- [x] 4.11 Return structured `{"steps": [...], "total_written": N}` response
- [x] 4.12 Handle graceful skip when gap < 0.1h or Binance unavailable (include `reason` key in skipped steps)

## 5. Management Console

- [x] 5.1 Remove `#DDL_OHLCV_PERIOD` CSS block from `src/market_data/api/rest/console.py`
- [x] 5.2 Remove `<select id="DDL_OHLCV_PERIOD">` HTML element from the action bar
- [x] 5.3 Remove `const ddlPeriod = document.getElementById('DDL_OHLCV_PERIOD')` JS reference
- [x] 5.4 Remove `ddlPeriod.disabled = !enabled` line from `setActionsEnabled`
- [x] 5.5 Replace the `BTN_UPDATE_OHLCV` click handler to call `POST /v1/admin/smart-update-ohlcv` with `{instrument_id: selectedInstrumentId}`
- [x] 5.6 Show "Updating…" loading state on the button during the request
- [x] 5.7 Build human-readable summary message from the `steps` array and display it inline
- [x] 5.8 Show Binance-unavailable note when `binance_availability` step is `"unavailable"`
- [x] 5.9 Refresh OHLCV sections after a successful response
- [x] 5.10 Show "OHLCV update failed: <error>" on HTTP or network error
- [x] 5.11 Re-enable the button with label "Update OHLCV Data" after request completes

## 6. Tests

- [x] 6.1 Unit test: `_aggregate_1m_to_1h` bucketing — correct open/high/low/close/volume for a full 60-candle hour bucket
- [x] 6.2 Unit test: `_aggregate_1m_to_1h` — partial bucket (mid-hour cutoff) produces one candle
- [x] 6.3 Unit test: writer upsert — real candle (`is_aggregated=False`) overwrites existing aggregated row
- [x] 6.4 Unit test: writer upsert — aggregated candle (`is_aggregated=True`) does not overwrite existing real row
- [x] 6.5 Integration test: `POST /v1/admin/smart-update-ohlcv` with mocked Binance returns correct step list and `total_written`
- [x] 6.6 Integration test: unknown `instrument_id` returns HTTP 404

## 7. Documentation

- [x] 7.1 Add `POST /v1/admin/smart-update-ohlcv` row to the Admin endpoints table in `README.md`
- [x] 7.2 Update the Management Console section in `README.md` — remove DDL_OHLCV_PERIOD mention, describe smart-update behaviour
- [x] 7.3 Update `docs/management-console.md` element reference table — remove `DDL_OHLCV_PERIOD`, note new button behaviour
- [x] 7.4 Add migration 030 row to the Database Schema table in `README.md`
