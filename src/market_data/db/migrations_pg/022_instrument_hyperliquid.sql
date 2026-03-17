-- 022_instrument_hyperliquid.sql
-- Hyperliquid perpetual pairs metadata per instrument and network

CREATE TABLE IF NOT EXISTS instrument_hyperliquid (
    instrument_id       TEXT                NOT NULL REFERENCES instruments(instrument_id),
    network             TEXT                NOT NULL CHECK (network IN ('mainnet', 'testnet')),
    hl_symbol           TEXT                NOT NULL,
    lot_size            DOUBLE PRECISION    NOT NULL,
    tick_size           DOUBLE PRECISION    NOT NULL,
    max_leverage        DOUBLE PRECISION    NOT NULL,
    is_active           BOOLEAN             NOT NULL DEFAULT TRUE,
    last_refreshed_at   TIMESTAMPTZ         NOT NULL,
    PRIMARY KEY (instrument_id, network)
);
