-- 010_cmc_static_tables.sql
-- CoinMarketCap static snapshot import tables

-- Tracks which snapshot timestamps have been fully imported (idempotency guard)
CREATE TABLE IF NOT EXISTS cmc_import_log (
    snapshot_ts  TIMESTAMPTZ NOT NULL PRIMARY KEY,
    imported_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-snapshot listing data: price, market-cap, supply, rank for each coin
CREATE TABLE IF NOT EXISTS cmc_listing_snapshots (
    snapshot_ts              TIMESTAMPTZ      NOT NULL,
    cmc_id                   INTEGER          NOT NULL,
    name                     TEXT,
    symbol                   TEXT,
    slug                     TEXT,
    cmc_rank                 INTEGER,
    num_market_pairs         INTEGER,
    date_added               TIMESTAMPTZ,
    max_supply               DOUBLE PRECISION,
    circulating_supply       DOUBLE PRECISION,
    total_supply             DOUBLE PRECISION,
    infinite_supply          BOOLEAN,
    self_rep_circulating     DOUBLE PRECISION,
    self_rep_market_cap      DOUBLE PRECISION,
    tvl_ratio                DOUBLE PRECISION,
    price                    DOUBLE PRECISION,
    volume_24h               DOUBLE PRECISION,
    volume_change_24h        DOUBLE PRECISION,
    pct_change_1h            DOUBLE PRECISION,
    pct_change_24h           DOUBLE PRECISION,
    pct_change_7d            DOUBLE PRECISION,
    pct_change_30d           DOUBLE PRECISION,
    pct_change_60d           DOUBLE PRECISION,
    pct_change_90d           DOUBLE PRECISION,
    market_cap               DOUBLE PRECISION,
    market_cap_dominance     DOUBLE PRECISION,
    fully_diluted_market_cap DOUBLE PRECISION,
    tvl                      DOUBLE PRECISION,
    last_updated             TIMESTAMPTZ,
    PRIMARY KEY (snapshot_ts, cmc_id)
);

-- Normalised coin tags (static; last-write wins per cmc_id+tag)
CREATE TABLE IF NOT EXISTS cmc_coin_tags (
    cmc_id  INTEGER NOT NULL,
    tag     TEXT    NOT NULL,
    PRIMARY KEY (cmc_id, tag)
);

-- Category master records from categories_data
CREATE TABLE IF NOT EXISTS cmc_categories (
    cmc_id             TEXT            NOT NULL PRIMARY KEY,
    name               TEXT,
    title              TEXT,
    description        TEXT,
    num_tokens         INTEGER,
    avg_price_change   DOUBLE PRECISION,
    market_cap         DOUBLE PRECISION,
    market_cap_change  DOUBLE PRECISION,
    volume             DOUBLE PRECISION,
    volume_change      DOUBLE PRECISION,
    last_updated       TIMESTAMPTZ
);

-- Many-to-many category ↔ coin associations from category_data
CREATE TABLE IF NOT EXISTS cmc_category_coins (
    category_id   TEXT    NOT NULL,
    cmc_coin_id   INTEGER NOT NULL,
    PRIMARY KEY (category_id, cmc_coin_id)
);

-- Canonical coin ↔ CMC-id mapping from map_data
CREATE TABLE IF NOT EXISTS cmc_map (
    cmc_id                INTEGER  NOT NULL PRIMARY KEY,
    rank                  INTEGER,
    name                  TEXT,
    symbol                TEXT,
    slug                  TEXT,
    is_active             INTEGER,
    status                INTEGER,
    first_historical_data TIMESTAMPTZ,
    last_historical_data  TIMESTAMPTZ,
    platform              TEXT
);

CREATE INDEX IF NOT EXISTS idx_cmc_map_slug ON cmc_map (slug);
CREATE INDEX IF NOT EXISTS idx_cmc_listing_snapshots_ts ON cmc_listing_snapshots (snapshot_ts);
