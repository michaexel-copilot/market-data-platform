-- 008_ohlcv.sql
-- Multi-interval OHLCV time-series table

CREATE TABLE IF NOT EXISTS ohlcv (
    instrument_id VARCHAR     NOT NULL,
    interval      VARCHAR     NOT NULL CHECK (interval IN ('1m', '5m', '1h', '1d')),
    ts            TIMESTAMPTZ NOT NULL,
    open          DOUBLE      NOT NULL,
    high          DOUBLE      NOT NULL,
    low           DOUBLE      NOT NULL,
    close         DOUBLE      NOT NULL,
    volume        DOUBLE,
    vwap          DOUBLE,
    trade_count   INTEGER,
    market_cap    DOUBLE,
    source        VARCHAR     NOT NULL,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, interval, ts)
);

-- Index for fast time-range queries per instrument+interval
CREATE INDEX IF NOT EXISTS idx_ohlcv_instrument_interval_ts
    ON ohlcv (instrument_id, interval, ts);
