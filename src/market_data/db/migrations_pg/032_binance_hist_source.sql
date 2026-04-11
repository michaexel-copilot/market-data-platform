-- 032_binance_hist_source.sql
-- Register Binance Historical as a named data source.
-- retrieval_priority = NULL → import-only, never used for live ingestion.

INSERT INTO data_source (data_source_id, name, short_name, base_url, api_page_url, retrieval_priority)
VALUES (6, 'Binance Historical', 'binance_hist', 'https://data.binance.vision', NULL, NULL)
ON CONFLICT (data_source_id) DO NOTHING;
