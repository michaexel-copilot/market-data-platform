## 1. Database Migrations

- [x] 1.1 Create `src/market_data/db/migrations/010_cmc_static_tables.sql` — tables `cmc_import_log`, `cmc_listing_snapshots`, `cmc_coin_tags`, `cmc_categories`, `cmc_category_coins`, `cmc_map`
- [x] 1.2 Create `src/market_data/db/migrations/011_instrument_crypto_cmc_columns.sql` — `ALTER TABLE instrument_crypto ADD COLUMN IF NOT EXISTS` for `cmc_id`, `cmc_slug`, `cmc_rank`

## 2. Core Importer Module

- [x] 2.1 Create `src/market_data/ingestion/import_coinmarketcap_static.py` with helper `_parse_float()` (comma→dot normalisation) and `_parse_list_repr()` / `_parse_dict_repr()` (ast.literal_eval wrappers)
- [x] 2.2 Implement `discover_snapshots(directory)` — glob `*_listing_data.tsv`, extract timestamp prefix, yield `SnapshotSet` namedtuples with paths for all four file types
- [x] 2.3 Implement `is_imported(conn, snapshot_ts)` and `mark_imported(conn, snapshot_ts)` — read/write `cmc_import_log`
- [x] 2.4 Implement `import_listing_data(conn, path, snapshot_ts)` — upsert into `cmc_listing_snapshots` and `cmc_coin_tags`
- [x] 2.5 Implement `import_map_data(conn, path)` — upsert into `cmc_map`
- [x] 2.6 Implement `import_categories_data(conn, path)` — upsert into `cmc_categories`
- [x] 2.7 Implement `import_category_data(conn, path)` — parse coins column with `ast.literal_eval`, upsert into `cmc_category_coins`
- [x] 2.8 Implement `enrich_instrument_crypto(conn)` — UPDATE `instrument_crypto` from `cmc_map` where slug matches `instrument_id`
- [x] 2.9 Implement `run_import(directory, dry_run=False)` — orchestrate discover → skip-if-imported → import all four files → mark imported → enrich; with progress logging every 100 snapshots

## 3. CLI Entry-Point

- [x] 3.1 Add `typer` app to `src/market_data/cli/__init__.py` with command `import-cmc-static [DIR] [--dry-run]`
- [x] 3.2 Wire CLI to `run_import()` from the importer module; validate that DIR exists and is a directory before calling

## 4. Tests

- [x] 4.1 Create `tests/test_import_coinmarketcap_static.py` with a fixture that writes minimal TSV files for all four patterns into a `tmp_path`
- [x] 4.2 Test `discover_snapshots` — finds the correct snapshot sets and handles missing siblings
- [x] 4.3 Test `import_listing_data` — comma-decimal normalisation, tag parsing, upsert idempotency
- [x] 4.4 Test `import_map_data` — upsert idempotency
- [x] 4.5 Test `import_categories_data` and `import_category_data` — upsert, malformed `coins` column skipped with warning
- [x] 4.6 Test `run_import` end-to-end — first run inserts rows; second run produces zero new rows (idempotency)
- [x] 4.7 Test `enrich_instrument_crypto` — matching slug updates cmc_id/rank; non-matching slug produces no new row

## 5. Documentation

- [x] 5.1 Create `docs/import-coinmarketcap-static.md` — file patterns, table schema overview, CLI usage, env vars, idempotency guarantee
