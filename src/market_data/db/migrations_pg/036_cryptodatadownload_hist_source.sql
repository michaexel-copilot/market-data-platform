-- 036_cryptodatadownload_hist_source.sql
-- Register CryptoDataDownload Historical as a named data source.
-- retrieval_priority = NULL → import-only, never used for live ingestion.

INSERT INTO data_source (data_source_id, name, short_name, base_url, api_page_url, retrieval_priority)
VALUES (7, 'CryptoDataDownload Historical', 'cdd_hist', 'https://www.cryptodatadownload.com', 'https://www.cryptodatadownload.com/data/binance/', NULL)
ON CONFLICT (data_source_id) DO NOTHING;
