-- 013_attribute_source_map.sql
-- Per-attribute data provenance tracking

CREATE TABLE IF NOT EXISTS attribute_source_map (
    instrument_id   VARCHAR      NOT NULL REFERENCES instruments(instrument_id),
    attribute_name  VARCHAR      NOT NULL,
    data_source_id  INTEGER      NOT NULL REFERENCES data_source(data_source_id),
    last_updated_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, attribute_name)
);
