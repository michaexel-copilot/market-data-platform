-- Subset of the production market_data schema (from `\d+`, 2026-10-17) that
-- ohlcv_backfill.py reads or writes. Used by tests/test_ohlcv_backfill_db.py only.
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE instruments (
    instrument_id text PRIMARY KEY,
    ticker        text NOT NULL,
    asset_class   text NOT NULL
);

CREATE SEQUENCE seq_data_source_id;
CREATE TABLE data_source (
    data_source_id integer PRIMARY KEY DEFAULT nextval('seq_data_source_id'),
    name           text NOT NULL,
    short_name     text NOT NULL,
    base_url       text NOT NULL
);

CREATE TABLE ohlcv_data_available (
    instrument_id  text    NOT NULL REFERENCES instruments(instrument_id),
    data_source_id integer NOT NULL REFERENCES data_source(data_source_id),
    has_1m boolean NOT NULL DEFAULT false,
    has_5m boolean NOT NULL DEFAULT false,
    has_1h boolean NOT NULL DEFAULT false,
    has_1d boolean NOT NULL DEFAULT false,
    PRIMARY KEY (instrument_id, data_source_id)
);

CREATE TABLE ohlcv (
    instrument_id text NOT NULL,
    interval      text NOT NULL,
    ts            timestamptz NOT NULL,
    open  double precision NOT NULL,
    high  double precision NOT NULL,
    low   double precision NOT NULL,
    close double precision NOT NULL,
    volume double precision,
    vwap   double precision,
    trade_count integer,
    market_cap  double precision,
    source      text NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    tick_1h bigint,
    tick_1d bigint,
    is_aggregated boolean NOT NULL DEFAULT false,
    tick_1m bigint,
    PRIMARY KEY (instrument_id, interval, ts),
    CONSTRAINT ohlcv_interval_check CHECK (interval = ANY (ARRAY['1m', '5m', '1h', '1d'])),
    CONSTRAINT ohlcv_price_sanity CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0
        AND high >= GREATEST(open, close) AND low <= LEAST(open, close) AND low <= high
        AND (volume IS NULL OR volume >= 0) AND (vwap IS NULL OR vwap >= 0)
        AND (trade_count IS NULL OR trade_count >= 0) AND (market_cap IS NULL OR market_cap >= 0)),
    CONSTRAINT ohlcv_tick_1d_not_null CHECK (interval <> '1d' OR tick_1d IS NOT NULL),
    CONSTRAINT ohlcv_tick_1h_not_null CHECK (interval <> '1h' OR tick_1h IS NOT NULL),
    CONSTRAINT ohlcv_tick_1m_not_null CHECK (interval <> '1m' OR tick_1m IS NOT NULL)
);
SELECT create_hypertable('ohlcv', 'ts');

INSERT INTO instruments VALUES ('bitcoin', 'BTC', 'crypto'), ('ethereum', 'ETH', 'crypto');
INSERT INTO data_source (name, short_name, base_url) VALUES
    ('Hyperliquid', 'hl', 'https://hyperliquid.xyz'),
    ('Kraken Historical', 'kraken_hist', 'https://support.kraken.com'),
    ('Binance Historical', 'binance_hist', 'https://data.binance.vision');
