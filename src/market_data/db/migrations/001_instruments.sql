-- 001_instruments.sql
-- Core instruments table for all asset classes

CREATE TABLE IF NOT EXISTS instruments (
    instrument_id   VARCHAR     NOT NULL,
    ticker          VARCHAR     NOT NULL,
    full_name       VARCHAR,
    description     TEXT,
    asset_class     VARCHAR     NOT NULL CHECK (asset_class IN (
                        'crypto', 'equity', 'etf', 'fx', 'commodity', 'index', 'future'
                    )),
    exchange        VARCHAR,
    sector          VARCHAR,
    industry        VARCHAR,
    quote_currency  VARCHAR,
    launch_date     DATE,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    logo_url        VARCHAR,
    website_url     VARCHAR,
    data_sources    JSON,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_instruments_ticker_exchange_class
    ON instruments (ticker, exchange, asset_class);
