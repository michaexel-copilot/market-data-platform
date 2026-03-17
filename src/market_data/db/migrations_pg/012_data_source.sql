-- 012_data_source.sql
-- Registry of known data providers

CREATE SEQUENCE IF NOT EXISTS seq_data_source_id START 1;

CREATE TABLE IF NOT EXISTS data_source (
    data_source_id     INTEGER      NOT NULL DEFAULT nextval('seq_data_source_id') PRIMARY KEY,
    name               TEXT         NOT NULL,
    short_name         TEXT         NOT NULL,
    base_url           TEXT         NOT NULL,
    api_page_url       TEXT,
    retrieval_priority INTEGER      -- NULL = source disabled; 0 = highest priority
);

-- Seed: CoinMarketCap
INSERT INTO data_source (data_source_id, name, short_name, base_url, api_page_url, retrieval_priority)
VALUES (1, 'CoinMarketCap', 'cmc', 'https://coinmarketcap.com', 'https://coinmarketcap.com/api/documentation/v1/', 0)
ON CONFLICT (data_source_id) DO NOTHING;
