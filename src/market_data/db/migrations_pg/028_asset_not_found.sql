-- Migration 028: Add asset_not_found table
-- Records (instrument_id, data_source, interval) combinations that returned HTTP 404.
-- The ingestion scheduler consults this table to suppress future fetch attempts.

CREATE TABLE IF NOT EXISTS asset_not_found (
    instrument_id  TEXT        NOT NULL,
    data_source    TEXT        NOT NULL,
    interval       TEXT        NOT NULL,
    url            TEXT        NOT NULL,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (instrument_id, data_source, interval)
);
