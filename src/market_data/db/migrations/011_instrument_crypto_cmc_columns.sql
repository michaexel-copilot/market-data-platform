-- 011_instrument_crypto_cmc_columns.sql
-- Add nullable CoinMarketCap-specific columns to instrument_crypto

ALTER TABLE instrument_crypto ADD COLUMN IF NOT EXISTS cmc_id   INTEGER;
ALTER TABLE instrument_crypto ADD COLUMN IF NOT EXISTS cmc_slug  VARCHAR;
ALTER TABLE instrument_crypto ADD COLUMN IF NOT EXISTS cmc_rank  INTEGER;
