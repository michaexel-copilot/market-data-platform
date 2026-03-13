-- 014_ticker_source_map.sql
-- Cross-source ticker disambiguation mapping

CREATE TABLE IF NOT EXISTS ticker_source_map (
    instrument_id   VARCHAR  NOT NULL REFERENCES instruments(instrument_id),
    data_source_id  INTEGER  NOT NULL REFERENCES data_source(data_source_id),
    source_ticker   VARCHAR  NOT NULL,
    is_canonical    BOOLEAN  NOT NULL DEFAULT FALSE,
    PRIMARY KEY (instrument_id, data_source_id)
);
