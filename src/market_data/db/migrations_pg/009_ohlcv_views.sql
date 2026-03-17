-- 009_ohlcv_views.sql
-- Derived weekly and monthly OHLCV plain views from daily data.
-- These use PostgreSQL-native array_agg ordering to get open (first) and
-- close (last) values without requiring TimescaleDB.
-- Migration 021 will replace these with TimescaleDB continuous aggregates
-- after the hypertable and extension are set up.

CREATE OR REPLACE VIEW ohlcv_weekly AS
SELECT
    instrument_id,
    '1w'                                                AS interval,
    date_trunc('week', ts)::TIMESTAMPTZ                 AS ts,
    (array_agg(open        ORDER BY ts ASC))[1]         AS open,
    max(high)                                           AS high,
    min(low)                                            AS low,
    (array_agg(close       ORDER BY ts DESC))[1]        AS close,
    sum(volume)                                         AS volume,
    CASE WHEN sum(volume) > 0
         THEN sum(volume * vwap) / sum(volume)
         ELSE NULL END                                  AS vwap,
    sum(trade_count)                                    AS trade_count,
    (array_agg(market_cap  ORDER BY ts DESC))[1]        AS market_cap,
    source,
    max(ingested_at)                                    AS ingested_at
FROM ohlcv
WHERE interval = '1d'
GROUP BY
    instrument_id,
    date_trunc('week', ts),
    source;


CREATE OR REPLACE VIEW ohlcv_monthly AS
SELECT
    instrument_id,
    '1mo'                                               AS interval,
    date_trunc('month', ts)::TIMESTAMPTZ                AS ts,
    (array_agg(open        ORDER BY ts ASC))[1]         AS open,
    max(high)                                           AS high,
    min(low)                                            AS low,
    (array_agg(close       ORDER BY ts DESC))[1]        AS close,
    sum(volume)                                         AS volume,
    CASE WHEN sum(volume) > 0
         THEN sum(volume * vwap) / sum(volume)
         ELSE NULL END                                  AS vwap,
    sum(trade_count)                                    AS trade_count,
    (array_agg(market_cap  ORDER BY ts DESC))[1]        AS market_cap,
    source,
    max(ingested_at)                                    AS ingested_at
FROM ohlcv
WHERE interval = '1d'
GROUP BY
    instrument_id,
    date_trunc('month', ts),
    source;
