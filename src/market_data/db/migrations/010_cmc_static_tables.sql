-- 010_cmc_static_tables.sql
-- CoinMarketCap static snapshot import tables

-- Tracks which snapshot timestamps have been fully imported (idempotency guard)
CREATE TABLE IF NOT EXISTS cmc_import_log (
    snapshot_ts  TIMESTAMPTZ NOT NULL PRIMARY KEY,
    imported_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-snapshot listing data: price, market-cap, supply, rank for each coin
CREATE TABLE IF NOT EXISTS cmc_listing_snapshots (
    snapshot_ts              TIMESTAMPTZ NOT NULL,
    cmc_id                   INTEGER     NOT NULL,
    name                     VARCHAR,
    symbol                   VARCHAR,
    slug                     VARCHAR,
    cmc_rank                 INTEGER,
    num_market_pairs         INTEGER,
    date_added               TIMESTAMPTZ,
    max_supply               DOUBLE,
    circulating_supply       DOUBLE,
    total_supply             DOUBLE,
    infinite_supply          BOOLEAN,
    self_rep_circulating     DOUBLE,
    self_rep_market_cap      DOUBLE,
    tvl_ratio                DOUBLE,
    price                    DOUBLE,
    volume_24h               DOUBLE,
    volume_change_24h        DOUBLE,
    pct_change_1h            DOUBLE,
    pct_change_24h           DOUBLE,
    pct_change_7d            DOUBLE,
    pct_change_30d           DOUBLE,
    pct_change_60d           DOUBLE,
    pct_change_90d           DOUBLE,
    market_cap               DOUBLE,
    market_cap_dominance     DOUBLE,
    fully_diluted_market_cap DOUBLE,
    tvl                      DOUBLE,
    last_updated             TIMESTAMPTZ,
    PRIMARY KEY (snapshot_ts, cmc_id)
);

-- Normalised coin tags (static; last-write wins per cmc_id+tag)
CREATE TABLE IF NOT EXISTS cmc_coin_tags (
    cmc_id  INTEGER NOT NULL,
    tag     VARCHAR NOT NULL,
    PRIMARY KEY (cmc_id, tag)
);

-- Category master records from categories_data
CREATE TABLE IF NOT EXISTS cmc_categories (
    cmc_id             VARCHAR NOT NULL PRIMARY KEY,
    name               VARCHAR,
    title              VARCHAR,
    description        VARCHAR,
    num_tokens         INTEGER,
    avg_price_change   DOUBLE,
    market_cap         DOUBLE,
    market_cap_change  DOUBLE,
    volume             DOUBLE,
    volume_change      DOUBLE,
    last_updated       TIMESTAMPTZ
);

-- Many-to-many category ↔ coin associations from category_data
CREATE TABLE IF NOT EXISTS cmc_category_coins (
    category_id   VARCHAR NOT NULL,
    cmc_coin_id   INTEGER NOT NULL,
    PRIMARY KEY (category_id, cmc_coin_id)
);

-- Canonical coin ↔ CMC-id mapping from map_data
CREATE TABLE IF NOT EXISTS cmc_map (
    cmc_id                INTEGER  NOT NULL PRIMARY KEY,
    rank                  INTEGER,
    name                  VARCHAR,
    symbol                VARCHAR,
    slug                  VARCHAR,
    is_active             INTEGER,
    status                INTEGER,
    first_historical_data TIMESTAMPTZ,
    last_historical_data  TIMESTAMPTZ,
    platform              VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_cmc_map_slug ON cmc_map (slug);
CREATE INDEX IF NOT EXISTS idx_cmc_listing_snapshots_ts ON cmc_listing_snapshots (snapshot_ts);
