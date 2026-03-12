-- 004_instrument_equity.sql
-- Equity-specific attributes

CREATE TABLE IF NOT EXISTS instrument_equity (
    instrument_id           VARCHAR NOT NULL PRIMARY KEY REFERENCES instruments(instrument_id),
    isin                    VARCHAR,
    cusip                   VARCHAR,
    figi                    VARCHAR,
    composite_figi          VARCHAR,
    mic_code                VARCHAR,
    sic_code                VARCHAR,
    country_of_incorporation VARCHAR,  -- ISO 3166-1 alpha-2
    shares_outstanding      BIGINT,
    float_shares            BIGINT
);
