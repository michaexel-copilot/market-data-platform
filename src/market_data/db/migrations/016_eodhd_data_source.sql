-- 016_eodhd_data_source.sql
-- Seed eodhd data source and populate ohlcv_data_available for existing crypto instruments

-- Seed: EOD Historical Data
INSERT OR IGNORE INTO data_source (data_source_id, name, short_name, base_url, api_page_url, retrieval_priority)
VALUES (2, 'EOD Historical Data', 'eodhd', 'https://eodhd.com', 'https://eodhd.com/financial-apis/', 1);

-- Seed ohlcv_data_available: eodhd covers all four native intervals
INSERT OR IGNORE INTO ohlcv_data_available (instrument_id, data_source_id, has_1m, has_5m, has_1h, has_1d)
SELECT i.instrument_id, 2, TRUE, TRUE, TRUE, TRUE
FROM instruments i
WHERE i.asset_class = 'crypto';

-- Seed ohlcv_data_available: CoinMarketCap covers daily only
INSERT OR IGNORE INTO ohlcv_data_available (instrument_id, data_source_id, has_1m, has_5m, has_1h, has_1d)
SELECT i.instrument_id, 1, FALSE, FALSE, FALSE, TRUE
FROM instruments i
WHERE i.asset_class = 'crypto';
