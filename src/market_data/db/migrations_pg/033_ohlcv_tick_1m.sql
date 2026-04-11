-- Migration 033: Add tick_1m column to ohlcv table
-- tick_1m is the number of 1-minute intervals elapsed since Unix epoch (1970-01-01T00:00:00Z)
-- Formula: EXTRACT(EPOCH FROM ts)::BIGINT / 60

-- Allow decompression of all chunks during backfill (production DB may have many
-- compressed chunks that exceed the default limit of 100k tuples per DML).
SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0;

-- Step 1: Add nullable column (IF NOT EXISTS makes this idempotent)
ALTER TABLE ohlcv ADD COLUMN IF NOT EXISTS tick_1m BIGINT;

-- Step 2: Backfill existing 1m rows (idempotent)
UPDATE ohlcv
   SET tick_1m = EXTRACT(EPOCH FROM ts)::BIGINT / 60
 WHERE interval = '1m';

-- Step 3: Drop constraint if it already exists (idempotency for re-runs), then add
ALTER TABLE ohlcv DROP CONSTRAINT IF EXISTS ohlcv_tick_1m_not_null;

ALTER TABLE ohlcv
    ADD CONSTRAINT ohlcv_tick_1m_not_null
    CHECK (interval != '1m' OR tick_1m IS NOT NULL);
