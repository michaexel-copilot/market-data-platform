-- 007_instrument_commodity.sql
-- Commodity / futures specific attributes

CREATE TABLE IF NOT EXISTS instrument_commodity (
    instrument_id   VARCHAR NOT NULL PRIMARY KEY REFERENCES instruments(instrument_id),
    unit_of_measure VARCHAR,
    contract_size   DOUBLE,
    delivery_month  VARCHAR  -- e.g. '2026-04'
);
