-- 009_ohlcv_views.sql
-- Derived weekly and monthly OHLCV views from daily data

CREATE OR REPLACE VIEW ohlcv_weekly AS
SELECT
    instrument_id,
    '1w'                                                          AS interval,
    -- Align to Monday: subtract (dayofweek - 1) days, where Monday=1
    ts::DATE - ((EXTRACT(DOW FROM ts)::INTEGER + 6) % 7) * INTERVAL '1 day' AS ts,
    first(open  ORDER BY ts)                                      AS open,
    max(high)                                                     AS high,
    min(low)                                                      AS low,
    last(close  ORDER BY ts)                                      AS close,
    sum(volume)                                                   AS volume,
    sum(volume * vwap) / NULLIF(sum(volume), 0)                   AS vwap,
    sum(trade_count)                                              AS trade_count,
    last(market_cap ORDER BY ts)                                  AS market_cap,
    source,
    max(ingested_at)                                              AS ingested_at
FROM ohlcv
WHERE interval = '1d'
GROUP BY
    instrument_id,
    ts::DATE - ((EXTRACT(DOW FROM ts)::INTEGER + 6) % 7) * INTERVAL '1 day',
    source;


CREATE OR REPLACE VIEW ohlcv_monthly AS
SELECT
    instrument_id,
    '1mo'                                                         AS interval,
    DATE_TRUNC('month', ts)                                       AS ts,
    first(open  ORDER BY ts)                                      AS open,
    max(high)                                                     AS high,
    min(low)                                                      AS low,
    last(close  ORDER BY ts)                                      AS close,
    sum(volume)                                                   AS volume,
    sum(volume * vwap) / NULLIF(sum(volume), 0)                   AS vwap,
    sum(trade_count)                                              AS trade_count,
    last(market_cap ORDER BY ts)                                  AS market_cap,
    source,
    max(ingested_at)                                              AS ingested_at
FROM ohlcv
WHERE interval = '1d'
GROUP BY
    instrument_id,
    DATE_TRUNC('month', ts),
    source;
