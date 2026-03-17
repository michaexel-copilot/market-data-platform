-- 008_ohlcv.sql
-- Multi-interval OHLCV time-series table

CREATE TABLE IF NOT EXISTS ohlcv (
    instrument_id TEXT            NOT NULL,
    interval      TEXT            NOT NULL CHECK (interval IN ('1m', '5m', '1h', '1d')),
    ts            TIMESTAMPTZ     NOT NULL,
    open          DOUBLE PRECISION NOT NULL,
    high          DOUBLE PRECISION NOT NULL,
    low           DOUBLE PRECISION NOT NULL,
    close         DOUBLE PRECISION NOT NULL,
    volume        DOUBLE PRECISION,
    vwap          DOUBLE PRECISION,
    trade_count   INTEGER,
    market_cap    DOUBLE PRECISION,
    source        TEXT            NOT NULL,
    ingested_at   TIMESTAMPTZ     NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, interval, ts)
);

-- Index for fast time-range queries per instrument+interval
CREATE INDEX IF NOT EXISTS idx_ohlcv_instrument_interval_ts
    ON ohlcv (instrument_id, interval, ts);
