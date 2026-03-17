-- 003_instrument_crypto.sql
-- Crypto-specific attributes

CREATE TABLE IF NOT EXISTS instrument_crypto (
    instrument_id       TEXT            NOT NULL PRIMARY KEY REFERENCES instruments(instrument_id),
    blockchain_network  TEXT,
    consensus_mechanism TEXT,
    total_supply        DOUBLE PRECISION,
    max_supply          DOUBLE PRECISION,
    circulating_supply  DOUBLE PRECISION,
    decimals            INTEGER,
    whitepaper_url      TEXT,
    github_url          TEXT
);
