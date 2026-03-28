-- 031_kraken_historical_source.sql
-- Register Kraken Historical as a named data source.
-- retrieval_priority = NULL → import-only, never used for live ingestion.

INSERT INTO data_source (data_source_id, name, short_name, base_url, api_page_url, retrieval_priority)
VALUES (5, 'Kraken Historical', 'kraken_hist', 'https://support.kraken.com/hc/en-us/articles/360047124832', NULL, NULL)
ON CONFLICT (data_source_id) DO NOTHING;
