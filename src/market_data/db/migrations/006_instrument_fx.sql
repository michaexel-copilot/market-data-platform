-- 006_instrument_fx.sql
-- FX / Forex pair attributes

CREATE TABLE IF NOT EXISTS instrument_fx (
    instrument_id  VARCHAR NOT NULL PRIMARY KEY REFERENCES instruments(instrument_id),
    base_currency  VARCHAR(3),
    quote_currency VARCHAR(3),
    pip_size       DOUBLE,
    session_type   VARCHAR CHECK (session_type IN ('24h', 'regional'))
);
