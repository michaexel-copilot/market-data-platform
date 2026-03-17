-- 004_instrument_equity.sql
-- Equity-specific attributes

CREATE TABLE IF NOT EXISTS instrument_equity (
    instrument_id            TEXT    NOT NULL PRIMARY KEY REFERENCES instruments(instrument_id),
    isin                     TEXT,
    cusip                    TEXT,
    figi                     TEXT,
    composite_figi           TEXT,
    mic_code                 TEXT,
    sic_code                 TEXT,
    country_of_incorporation TEXT,  -- ISO 3166-1 alpha-2
    shares_outstanding       BIGINT,
    float_shares             BIGINT
);
