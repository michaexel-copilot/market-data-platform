# CoinMarketCap Static Importer

## Purpose
Batch import of pre-downloaded CoinMarketCap TSV snapshot files into dedicated DuckDB tables, with optional enrichment of the instrument registry.

## Requirements

### Requirement: Discover snapshot sets by directory scan
The importer SHALL scan a given directory for files matching `*_listing_data.tsv` to
discover snapshot timestamps, then derive the sibling `*_map_data.tsv`,
`*_categories_data.tsv`, and `*_category_data.tsv` paths from the same prefix.  Missing
sibling files SHALL be logged as warnings and the import of that partial snapshot SHALL
continue with the available files.

#### Scenario: Full snapshot set present
- **WHEN** all four sibling TSV files share the same `<date>_<time>` prefix
- **THEN** all four are processed as one atomic snapshot set

#### Scenario: Sibling file missing
- **WHEN** a snapshot prefix has a `listing_data` file but no `map_data` file
- **THEN** the importer logs a WARNING and imports only the three present files; it does not abort

#### Scenario: Empty directory
- **WHEN** the target directory contains no `*_listing_data.tsv` files
- **THEN** the importer logs an INFO message "No snapshots found" and exits with code 0

---

### Requirement: Idempotent snapshot ingestion
The importer SHALL maintain a `cmc_import_log` table recording which snapshot timestamps
have been fully processed.  Re-running on an already-imported snapshot set SHALL produce
zero new rows in any CMC table.

#### Scenario: First import of a snapshot
- **WHEN** a snapshot timestamp is not present in `cmc_import_log`
- **THEN** all rows from that snapshot are upserted and the timestamp is recorded in `cmc_import_log`

#### Scenario: Re-import of an already-processed snapshot
- **WHEN** a snapshot timestamp is present in `cmc_import_log`
- **THEN** the importer skips all file reads for that snapshot and logs DEBUG "Skipping already imported snapshot <ts>"

---

### Requirement: Parse listing_data TSV
The importer SHALL read `listing_data` TSV files using `csv.DictReader` with tab delimiter.
Numeric fields that use comma as decimal separator SHALL be normalised to dot before casting
to float.  The `tags` column (Python list repr) SHALL be parsed via `ast.literal_eval`.  
Each row SHALL produce one upsert into `cmc_listing_snapshots` and zero or more upserts
into `cmc_coin_tags`.

#### Scenario: Numeric comma-decimal normalised
- **WHEN** a listing row contains `price` = `"114344,90"`
- **THEN** the stored value is the float `114344.90`

#### Scenario: Tags column parsed into normalised rows
- **WHEN** a listing row contains `tags` = `"['mineable', 'pow', 'sha-256']"`
- **THEN** three rows are upserted into `cmc_coin_tags`: `(cmc_id, 'mineable')`, `(cmc_id, 'pow')`, `(cmc_id, 'sha-256')`

#### Scenario: Missing or null tags
- **WHEN** a listing row has an empty or null `tags` column
- **THEN** no rows are inserted into `cmc_coin_tags` for that coin; the listing snapshot row is still inserted

---

### Requirement: Parse map_data TSV
The importer SHALL read `map_data` TSV files and upsert one row per `cmc_id` into
`cmc_map`.  Because `map_data` is a full registry snapshot, later snapshots MAY overwrite
earlier data for the same `cmc_id`.

#### Scenario: Map row inserted
- **WHEN** a map_data row is read with a previously unseen `cmc_id`
- **THEN** a row is inserted into `cmc_map` with `id`, `rank`, `name`, `symbol`, `slug`, `is_active`, `status`, `first_historical_data`, `last_historical_data`

#### Scenario: Map row updated on re-import
- **WHEN** the same `cmc_id` appears in a later snapshot
- **THEN** the existing `cmc_map` row is updated via `ON CONFLICT DO UPDATE`

---

### Requirement: Parse categories_data TSV
The importer SHALL read `categories_data` TSV files and upsert one row per `id` into
`cmc_categories`.

#### Scenario: Category upserted
- **WHEN** a categories_data row is read
- **THEN** `cmc_categories` is updated with `id`, `name`, `title`, `description`, `num_tokens`, `avg_price_change`, `market_cap`, `market_cap_change`, `volume`, `volume_change`, `last_updated`

---

### Requirement: Parse category_data TSV
The importer SHALL read `category_data` TSV files where each row represents one coin within
a category.  The `coins` column is a Python dict repr and SHALL be parsed via
`ast.literal_eval`.  The importer SHALL upsert `(category_id, cmc_coin_id)` pairs into
`cmc_category_coins`.

#### Scenario: Coin-category association upserted
- **WHEN** a category_data row is read with `id=<category_id>` and a parsed `coins` dict containing `id=<coin_id>`
- **THEN** a row `(category_id, coin_id)` is upserted into `cmc_category_coins`

#### Scenario: Malformed coins column
- **WHEN** a category_data row's `coins` column cannot be parsed by `ast.literal_eval`
- **THEN** the importer logs a WARNING with the row number and category id, skips that row, and continues

---

### Requirement: Enrich instrument_crypto with CMC metadata
After ingesting listing snapshots, the importer SHALL update `instrument_crypto` rows where
the `slug` from `cmc_map` matches `instrument_id` in `instruments`, setting `cmc_id`,
`cmc_slug`, and `cmc_rank` (latest rank from `cmc_map`).

#### Scenario: Slug match enriches instrument
- **WHEN** `cmc_map.slug` equals an existing `instruments.instrument_id`
- **THEN** the corresponding `instrument_crypto` row is updated with `cmc_id`, `cmc_slug`, and `cmc_rank`

#### Scenario: No matching instrument
- **WHEN** a CMC slug has no corresponding `instruments` row
- **THEN** no row is created; the importer logs DEBUG "No instrument match for slug <slug>"

---

### Requirement: CLI entry-point
The system SHALL expose a CLI command `market-data import-cmc-static [DIR]` that runs the
full import pipeline.  `DIR` defaults to the environment variable `CMC_STATIC_DIR`.  The
command SHALL accept a `--dry-run` flag that parses and validates files without writing to
the database.
