-- 024_instrument_source_intersection.sql
-- Tracks which data sources cover each instrument (for intersection filtering)

CREATE TABLE IF NOT EXISTS instrument_source_intersection (
    instrument_id     TEXT NOT NULL REFERENCES instruments(instrument_id) ON DELETE CASCADE,
    source_short_name TEXT NOT NULL,
    PRIMARY KEY (instrument_id, source_short_name)
);
