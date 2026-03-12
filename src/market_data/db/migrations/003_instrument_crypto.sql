-- 003_instrument_crypto.sql
-- Crypto-specific attributes

CREATE TABLE IF NOT EXISTS instrument_crypto (
    instrument_id       VARCHAR NOT NULL PRIMARY KEY REFERENCES instruments(instrument_id),
    blockchain_network  VARCHAR,
    consensus_mechanism VARCHAR,
    total_supply        DOUBLE,
    max_supply          DOUBLE,
    circulating_supply  DOUBLE,
    decimals            INTEGER,
    whitepaper_url      VARCHAR,
    github_url          VARCHAR
);
