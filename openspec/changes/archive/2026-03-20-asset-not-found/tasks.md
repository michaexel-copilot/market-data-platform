## 1. Database Migration

- [x] 1.1 Create migration `028_asset_not_found.sql` with `CREATE TABLE asset_not_found (instrument_id TEXT NOT NULL, data_source TEXT NOT NULL, interval TEXT NOT NULL, url TEXT NOT NULL, first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (instrument_id, data_source, interval))`

## 2. DB Helper Module

- [x] 2.1 Create `src/market_data/db/asset_not_found.py` with `record_not_found(conn, instrument_id, data_source, interval, url)` — upsert using `INSERT … ON CONFLICT (instrument_id, data_source, interval) DO UPDATE SET last_seen_at = NOW()`
- [x] 2.2 Implement `load_blocked(conn, interval) -> frozenset[tuple[str, str]]` in the same module — returns all `(instrument_id, data_source)` pairs for the given interval

## 3. Ingestion Layer Update

- [x] 3.1 In `src/market_data/ingestion/jobs.py`, call `load_blocked(conn, interval)` once before the connector/instrument loops in `_run_interval_job` and store the result in a local `blocked` variable
- [x] 3.2 Add a `if (instrument_id, conn.name) in blocked: continue` guard inside the inner loop, before calling `conn.fetch_ohlcv`
- [x] 3.3 Add a `elif exc.response.status_code == 404:` branch in the `httpx.HTTPStatusError` handler that calls `record_not_found(...)`, logs an `INFO` message, and continues to the next instrument (no `break`)

## 4. Apply Migration

- [x] 4.1 Run `028_asset_not_found.sql` against the production database and verify the `asset_not_found` table is created

## 5. Tests

- [x] 5.1 Add `test_asset_not_found_record_and_load` in `tests/test_migrations.py` (or a dedicated test file) — inserts via `record_not_found`, verifies row exists, calls again to verify `last_seen_at` update, verifies `load_blocked` returns the pair
- [x] 5.2 Add `test_404_is_recorded_and_fetch_suppressed` in `tests/test_connectors.py` or a new `tests/test_asset_not_found.py` — mock connector raises `HTTPStatusError(404)`, assert `record_not_found` is called; on next job run the instrument is skipped
- [x] 5.3 Run the full test suite and confirm all tests pass
