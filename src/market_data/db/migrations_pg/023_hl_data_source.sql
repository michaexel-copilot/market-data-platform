-- 023_hl_data_source.sql
-- Seed Hyperliquid as a data source

INSERT INTO data_source (data_source_id, name, short_name, base_url, api_page_url, retrieval_priority)
VALUES (3, 'Hyperliquid', 'hl', 'https://hyperliquid.xyz', NULL, NULL)
ON CONFLICT (data_source_id) DO NOTHING;
