-- Migration 034: Persist per-instrument per-interval OHLCV update settings

CREATE TABLE IF NOT EXISTS ohlcv_update_settings (
    instrument_id VARCHAR NOT NULL REFERENCES instruments(instrument_id) ON DELETE CASCADE,
    interval VARCHAR NOT NULL,
    auto_update BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (instrument_id, interval)
);
