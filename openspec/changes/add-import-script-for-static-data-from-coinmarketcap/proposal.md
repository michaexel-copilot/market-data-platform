## Why

The platform already fetches live CoinMarketCap data via the API connector, but a large
archive of static snapshot exports (TSV files dating from August 2025 onwards) exists on
`/mnt/ds420/data/krypto/coinmarketcap/01_download` and is not yet ingested. Loading this
history enriches the instrument registry with CoinMarketCap-specific metadata (rank,
supply figures, tags, category memberships) and enables full historical replay without
consuming API quota.

## What Changes

- New Python import script `src/market_data/ingestion/import_coinmarketcap_static.py`
  that reads the four TSV snapshot patterns and loads them into DuckDB.
- New DB migrations for tables that do not yet exist:
  - `cmc_listing_snapshots` — per-snapshot price/market-cap/volume data for each coin
    (idempotent upsert on `(snapshot_ts, cmc_id)`).
  - `cmc_coin_tags` — normalised tag list derived from `listing_data` tags column.
  - `cmc_categories` — category master data from `categories_data`.
  - `cmc_category_coins` — many-to-many from `category_data` coins column.
  - `cmc_map` — coin-to-CoinMarketCap-id mapping with historical-data date range from
    `map_data`.
- Enrich existing `instrument_crypto` rows with `cmc_id`, `cmc_rank`, `cmc_slug` where
  they match on symbol (non-breaking, nullable columns added via migration).
- CLI entry-point `market-data import-cmc-static` wired through the existing CLI module.
- Documentation `docs/import-coinmarketcap-static.md` covering file patterns, table
  design, and CLI usage.

## Capabilities

### New Capabilities

- `coinmarketcap-static-importer`: Batch import script that reads the four CMC snapshot
  TSV file patterns (`listing_data`, `map_data`, `categories_data`, `category_data`) into
  DuckDB tables, with idempotent upsert behaviour and progress logging.

### Modified Capabilities

- `instrument-registry`: Additional nullable columns (`cmc_id`, `cmc_rank`, `cmc_slug`)
  added to `instrument_crypto`; enrichment step populates them from `listing_data`.
- `data-source-connectors`: Document the static-file import as a complementary ingestion
  path alongside the live API connector.

## Impact

- **DB migrations**: Two new migration SQL files (010_cmc_static_tables.sql,
  011_instrument_crypto_cmc_columns.sql).
- **Code**: New module `src/market_data/ingestion/import_coinmarketcap_static.py`;
  minor additions to `src/market_data/cli/__init__.py`.
- **Tests**: New `tests/test_import_coinmarketcap_static.py` using a small fixture TSV.
- **Dependencies**: No new third-party packages — `duckdb`, `csv`/`pathlib` (stdlib) are
  sufficient.
- **Data volume**: Each snapshot set is ~4 TSV files; the importer is designed to be
  re-run safely (upsert on natural keys).
