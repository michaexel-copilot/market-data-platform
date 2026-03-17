-- 021_ohlcv_continuous_aggregates.sql
-- Replace the plain ohlcv_weekly and ohlcv_monthly views from migration 009
-- with TimescaleDB continuous aggregates.
--
-- Continuous aggregates are materialized automatically in the background and
-- support much faster queries than plain views over large hypertables.
-- The time_bucket('1 week', ts) call aligns to ISO weeks (Monday start).

DROP VIEW IF EXISTS ohlcv_weekly;
DROP VIEW IF EXISTS ohlcv_monthly;

CREATE MATERIALIZED VIEW ohlcv_weekly
WITH (timescaledb.continuous) AS
SELECT
    instrument_id,
    '1w'::TEXT                                              AS interval,
    time_bucket('1 week', ts)                               AS ts,
    first(open,       ts)                                   AS open,
    max(high)                                               AS high,
    min(low)                                                AS low,
    last(close,       ts)                                   AS close,
    sum(volume)                                             AS volume,
    CASE WHEN sum(volume) > 0
         THEN sum(volume * vwap) / sum(volume)
         ELSE NULL END                                      AS vwap,
    sum(trade_count)                                        AS trade_count,
    last(market_cap,  ts)                                   AS market_cap,
    source,
    max(ingested_at)                                        AS ingested_at
FROM ohlcv
WHERE interval = '1d'
GROUP BY instrument_id, time_bucket('1 week', ts), source;

SELECT add_continuous_aggregate_policy(
    'ohlcv_weekly',
    start_offset      => INTERVAL '3 weeks',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 day',
    if_not_exists     => TRUE
);


CREATE MATERIALIZED VIEW ohlcv_monthly
WITH (timescaledb.continuous) AS
SELECT
    instrument_id,
    '1mo'::TEXT                                             AS interval,
    time_bucket('1 month', ts)                              AS ts,
    first(open,       ts)                                   AS open,
    max(high)                                               AS high,
    min(low)                                                AS low,
    last(close,       ts)                                   AS close,
    sum(volume)                                             AS volume,
    CASE WHEN sum(volume) > 0
         THEN sum(volume * vwap) / sum(volume)
         ELSE NULL END                                      AS vwap,
    sum(trade_count)                                        AS trade_count,
    last(market_cap,  ts)                                   AS market_cap,
    source,
    max(ingested_at)                                        AS ingested_at
FROM ohlcv
WHERE interval = '1d'
GROUP BY instrument_id, time_bucket('1 month', ts), source;

SELECT add_continuous_aggregate_policy(
    'ohlcv_monthly',
    start_offset      => INTERVAL '3 months',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 day',
    if_not_exists     => TRUE
);
