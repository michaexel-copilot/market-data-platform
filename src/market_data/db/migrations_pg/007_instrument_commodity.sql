-- 007_instrument_commodity.sql
-- Commodity / futures specific attributes

CREATE TABLE IF NOT EXISTS instrument_commodity (
    instrument_id   TEXT            NOT NULL PRIMARY KEY REFERENCES instruments(instrument_id),
    unit_of_measure TEXT,
    contract_size   DOUBLE PRECISION,
    delivery_month  TEXT  -- e.g. '2026-04'
);
