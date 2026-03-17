-- 019_ohlcv_hypertable.sql
-- Convert ohlcv to a TimescaleDB hypertable with monthly chunks,
-- add a hash dimension on instrument_id (4 partitions for parallelism),
-- configure columnar compression for chunks older than 7 days.

SELECT create_hypertable(
    'ohlcv',
    by_range('ts', INTERVAL '1 month'),
    if_not_exists => TRUE
);

SELECT add_dimension(
    'ohlcv',
    by_hash('instrument_id', 4),
    if_not_exists => TRUE
);

ALTER TABLE ohlcv SET (
    timescaledb.compress,
    timescaledb.compress_orderby  = 'ts DESC',
    timescaledb.compress_segmentby = 'instrument_id, interval'
);

SELECT add_compression_policy('ohlcv', INTERVAL '7 days', if_not_exists => TRUE);
