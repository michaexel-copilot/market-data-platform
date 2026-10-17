-- OHLCV store for ohlcv_backfill.py. Idempotent: safe to run against an existing
-- database. "{table}" is replaced with OHLCV_TABLE (default "ohlcv").
-- If the table already exists with other column names, CREATE TABLE is skipped and
-- the index/views below will fail loudly; adapt the names there instead.

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS {table} (
    coin          text             NOT NULL,   -- slug, e.g. 'bitcoin'
    interval      text             NOT NULL,   -- '1m','5m','15m','1h','4h','1d'
    source        text             NOT NULL,   -- 'binance','kraken','okx','hyperliquid',...
    ts            timestamptz      NOT NULL,   -- candle open time (UTC)
    open          double precision NOT NULL,
    high          double precision NOT NULL,
    low           double precision NOT NULL,
    close         double precision NOT NULL,
    volume        double precision,
    trade_count   bigint,
    vwap          double precision,
    is_aggregated boolean          NOT NULL DEFAULT false
);

SELECT create_hypertable('{table}', 'ts', chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE);

-- Upsert key used by ON CONFLICT in the loader.
CREATE UNIQUE INDEX IF NOT EXISTS {table}_series_ts_uq ON {table} (coin, interval, source, ts);

-- Compress chunks older than 30 days (1m history for hundreds of pairs is large).
ALTER TABLE {table} SET (timescaledb.compress, timescaledb.compress_segmentby = 'coin, interval, source',
                         timescaledb.compress_orderby = 'ts');
SELECT add_compression_policy('{table}', INTERVAL '30 days', if_not_exists => TRUE);

-- Depth, fill ratio and staleness per series (replaces the manual Excel overview).
CREATE OR REPLACE VIEW {table}_coverage AS
SELECT coin, interval, source,
       min(ts)  AS first_ts,
       max(ts)  AS last_ts,
       count(*) AS rows,
       round((count(*) / (extract(epoch FROM max(ts) - min(ts))
             / CASE interval WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
                             WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END + 1))::numeric, 3) AS fill_ratio,
       now() - max(ts) AS lag
FROM {table}
GROUP BY coin, interval, source;

-- Every hole inside a series (gap between consecutive candles > 1 interval).
-- Full scan: filter by coin/interval when querying large tables.
CREATE OR REPLACE VIEW {table}_gaps AS
SELECT coin, interval, source, prev_ts AS gap_after, ts AS gap_before, ts - prev_ts AS gap
FROM (
    SELECT coin, interval, source, ts,
           lag(ts) OVER (PARTITION BY coin, interval, source ORDER BY ts) AS prev_ts
    FROM {table}
) s
WHERE prev_ts IS NOT NULL
  AND ts - prev_ts > CASE interval WHEN '1m' THEN INTERVAL '1 minute' WHEN '5m' THEN INTERVAL '5 minutes'
                                   WHEN '15m' THEN INTERVAL '15 minutes' WHEN '1h' THEN INTERVAL '1 hour'
                                   WHEN '4h' THEN INTERVAL '4 hours' ELSE INTERVAL '1 day' END;

-- Daily candles derived from hourly ones, for series that only have deep 1h history.
CREATE MATERIALIZED VIEW IF NOT EXISTS {table}_1d_from_1h
WITH (timescaledb.continuous) AS
SELECT coin, source,
       time_bucket(INTERVAL '1 day', ts) AS ts,
       first(open, ts) AS open, max(high) AS high, min(low) AS low, last(close, ts) AS close,
       sum(volume) AS volume, sum(trade_count) AS trade_count, count(*) AS hours
FROM {table}
WHERE interval = '1h'
GROUP BY coin, source, time_bucket(INTERVAL '1 day', ts)
WITH NO DATA;

SELECT add_continuous_aggregate_policy('{table}_1d_from_1h',
       start_offset => INTERVAL '7 days', end_offset => INTERVAL '1 hour',
       schedule_interval => INTERVAL '1 hour', if_not_exists => TRUE);
