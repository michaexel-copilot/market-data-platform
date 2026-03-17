-- 002_instrument_identifiers.sql
-- Cross-reference table for all external identifiers per instrument

CREATE TABLE IF NOT EXISTS instrument_identifiers (
    instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
    id_type       TEXT NOT NULL CHECK (id_type IN (
                      'isin', 'cusip', 'figi', 'composite_figi', 'mic_code',
                      'coingecko_id', 'cmc_id', 'coincodex_id',
                      'contract_address', 'ticker_exchange'
                  )),
    id_value      TEXT NOT NULL,
    chain         TEXT,  -- only for contract_address: e.g. 'ethereum'
    PRIMARY KEY (instrument_id, id_type, id_value)
);

CREATE INDEX IF NOT EXISTS idx_identifiers_type_value
    ON instrument_identifiers (id_type, id_value);
