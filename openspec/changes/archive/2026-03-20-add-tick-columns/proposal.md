## Why

Detecting gaps and duplicates in the OHLCV time series requires complex timestamp arithmetic per interval. A pre-computed `tick` column — an integer counting intervals elapsed since Unix epoch — makes gap and duplicate detection trivially simple with integer arithmetic or uniqueness constraints.

## What Changes

- Add a `tick_1h` column (`BIGINT NOT NULL`) to the `ohlcv` table, representing the number of 1-hour intervals elapsed since Unix epoch (1970-01-01T00:00:00Z)
- Backfill `tick_1h` for all existing rows with `interval = '1h'`
- Update ingestion logic to populate `tick_1h` when inserting or upserting 1h candles

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `time-series-ohlcv`: The `ohlcv` table schema gains a `tick_1h` column (`BIGINT NOT NULL`); upsert requirements are updated to require this column to be populated for `interval = '1h'` rows

## Impact

- **Database**: `ohlcv` table schema migration to add `tick_1h BIGINT NOT NULL`; backfill migration required for existing `interval = '1h'` rows (`tick_1h = extract(epoch from ts)::BIGINT / 3600`)
- **Ingestion layer**: OHLCV writers must compute and supply `tick_1h` when writing 1h bars
- **Tests**: Existing OHLCV upsert and range query tests need updating to include the new column
