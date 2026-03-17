-- 001_instruments.sql
-- Core instruments table for all asset classes

CREATE TABLE IF NOT EXISTS instruments (
    instrument_id   TEXT        NOT NULL,
    ticker          TEXT        NOT NULL,
    full_name       TEXT,
    description     TEXT,
    asset_class     TEXT        NOT NULL CHECK (asset_class IN (
                        'crypto', 'equity', 'etf', 'fx', 'commodity', 'index', 'future'
                    )),
    exchange        TEXT,
    sector          TEXT,
    industry        TEXT,
    quote_currency  TEXT,
    launch_date     DATE,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    logo_url        TEXT,
    website_url     TEXT,
    data_sources    JSONB,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_instruments_ticker_exchange_class
    ON instruments (ticker, exchange, asset_class);
