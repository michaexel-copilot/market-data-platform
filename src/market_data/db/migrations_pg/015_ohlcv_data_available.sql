-- 015_ohlcv_data_available.sql
-- Tracks which native OHLCV intervals each data source covers per instrument

CREATE TABLE IF NOT EXISTS ohlcv_data_available (
    instrument_id  TEXT    NOT NULL REFERENCES instruments(instrument_id),
    data_source_id INTEGER NOT NULL REFERENCES data_source(data_source_id),
    has_1m         BOOLEAN NOT NULL DEFAULT FALSE,
    has_5m         BOOLEAN NOT NULL DEFAULT FALSE,
    has_1h         BOOLEAN NOT NULL DEFAULT FALSE,
    has_1d         BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (instrument_id, data_source_id)
);
