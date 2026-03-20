## 1. Database Migration

- [x] 1.1 Create `src/market_data/db/migrations_pg/026_ohlcv_tick_1h.sql` with three steps: (a) `ADD COLUMN tick_1h BIGINT`, (b) `UPDATE` backfill for `interval = '1h'`, (c) `ADD CONSTRAINT ohlcv_tick_1h_not_null CHECK (interval != '1h' OR tick_1h IS NOT NULL) NOT VALID` + `VALIDATE CONSTRAINT`
- [x] 1.2 Verify migration runs cleanly against the test database (`pytest tests/test_migrations.py`)

## 2. Model Update

- [x] 2.1 Add `tick_1h: int | None = None` field to `OHLCVRecord` in `src/market_data/models/ohlcv.py`

## 3. Writer Update

- [x] 3.1 In `src/market_data/ingestion/writer.py`, compute `tick_1h = int(record.ts.timestamp()) // 3600 if record.interval == Interval.H1 else None` for each record
- [x] 3.2 Add `tick_1h` to the INSERT column list and VALUES tuple in the upsert SQL
- [x] 3.3 Add `tick_1h = excluded.tick_1h` to the `ON CONFLICT DO UPDATE SET` clause

## 4. Tests

- [x] 4.1 Add `test_ohlcv_tick_1h_column_exists` to `tests/test_migrations.py` asserting the column is present after migration
- [x] 4.2 Add `test_ohlcv_tick_1h_backfill` to `tests/test_migrations.py` asserting no `interval = '1h'` row has `tick_1h IS NULL` after migration
- [x] 4.3 Add a writer unit test asserting that a 1h `OHLCVRecord` produces the correct `tick_1h` value
- [x] 4.4 Add a writer unit test asserting that a non-1h `OHLCVRecord` produces `tick_1h = NULL`
- [x] 4.5 Run full test suite and confirm all tests pass (`pytest`)
