-- 020_cmc_listing_snapshots_hypertable.sql
-- Convert cmc_listing_snapshots to a TimescaleDB hypertable with weekly chunks.
-- CMC snapshots are typically imported once per day, so weekly chunks are appropriate.

SELECT create_hypertable(
    'cmc_listing_snapshots',
    by_range('snapshot_ts', INTERVAL '1 week'),
    if_not_exists => TRUE
);
