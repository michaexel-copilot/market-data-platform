-- 025_stg_cryptocompare_1h.sql
-- CryptoCompare data source registration and staging table for hourly OHLCV flat files

-- Seed: CryptoCompare (retrieval_priority NULL = source disabled for live ingestion, import-only)
INSERT INTO data_source (data_source_id, name, short_name, base_url, api_page_url, retrieval_priority)
VALUES (4, 'CryptoCompare', 'cryptocompare', 'https://www.cryptocompare.com', NULL, NULL)
ON CONFLICT (data_source_id) DO NOTHING;

-- Staging table for CryptoCompare hourly OHLCV flat files
-- Retained permanently for re-runs and auditing; volume_btc preserved here only.
CREATE TABLE IF NOT EXISTS stg_cryptocompare_1h (
    instrument_id   TEXT             NOT NULL,
    unix_timestamp  BIGINT           NOT NULL,
    datetime        TIMESTAMPTZ      NOT NULL,
    open            DOUBLE PRECISION NOT NULL,
    high            DOUBLE PRECISION NOT NULL,
    close           DOUBLE PRECISION NOT NULL,
    low             DOUBLE PRECISION NOT NULL,
    volume_usd      DOUBLE PRECISION,
    volume_btc      DOUBLE PRECISION,
    imported_at     TIMESTAMPTZ      NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, unix_timestamp)
);
