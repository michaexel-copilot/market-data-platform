# Instrument Registry

## Purpose

Defines the schema and behaviour of the canonical instrument registry, including the core instruments table, asset-class-specific attribute tables, external identifier cross-referencing, and symbol resolution.

## Requirements

### Requirement: Instrument core record
The system SHALL maintain a canonical `instruments` table that stores one row per tradeable instrument with fields: `instrument_id` (UUID, primary key), `ticker`, `full_name`, `description`, `asset_class`, `exchange`, `sector`, `industry`, `quote_currency`, `launch_date`, `is_active`, `logo_url`, `website_url`, `data_sources` (JSON array), `first_seen_at`, `last_updated_at`.

#### Scenario: New instrument inserted
- **WHEN** an instrument is ingested for the first time
- **THEN** a row is created in `instruments` with a generated UUID `instrument_id`, `is_active = TRUE`, and `first_seen_at` set to the current UTC timestamp

#### Scenario: Duplicate instrument skipped
- **WHEN** an ingestion run attempts to insert an instrument that already exists (matched by `ticker` + `exchange` + `asset_class`)
- **THEN** the existing row is updated (`last_updated_at`, mutable fields) rather than creating a duplicate

#### Scenario: Delisted instrument soft-deleted
- **WHEN** a provider signals that an instrument is no longer active
- **THEN** `is_active` is set to `FALSE` and `last_updated_at` is updated; the row is NOT physically deleted

---

### Requirement: Asset-class-specific attribute tables
The system SHALL maintain separate per-asset-class attribute tables (`instrument_crypto`, `instrument_equity`, `instrument_etf`, `instrument_fx`, `instrument_commodity`) each with a foreign key `instrument_id` referencing `instruments`. Fields are defined per the proposal's Static Fields Model.  The `instrument_crypto` table SHALL additionally contain three nullable CMC-specific columns: `cmc_id INTEGER`, `cmc_slug VARCHAR`, `cmc_rank INTEGER`.

#### Scenario: Crypto instrument attributes stored
- **WHEN** a crypto instrument is ingested
- **THEN** a corresponding row is inserted or updated in `instrument_crypto` with `blockchain_network`, `consensus_mechanism`, `total_supply`, `max_supply`, `circulating_supply`, `decimals`, `whitepaper_url`, `github_url`

#### Scenario: Equity instrument attributes stored
- **WHEN** an equity instrument is ingested
- **THEN** a corresponding row is inserted or updated in `instrument_equity` with `isin`, `cusip`, `figi`, `composite_figi`, `mic_code`, `sic_code`, `country_of_incorporation`, `shares_outstanding`, `float_shares`

#### Scenario: Missing optional fields allowed
- **WHEN** a provider does not supply an optional attribute (e.g. `whitepaper_url`)
- **THEN** the field is stored as `NULL`; the record is still accepted

#### Scenario: CMC columns default to NULL
- **WHEN** a new `instrument_crypto` row is inserted without CMC enrichment
- **THEN** `cmc_id`, `cmc_slug`, and `cmc_rank` are stored as `NULL`

#### Scenario: CMC enrichment populates columns
- **WHEN** the CMC static importer finds a slug match between `cmc_map` and `instruments`
- **THEN** `instrument_crypto.cmc_id`, `cmc_slug`, and `cmc_rank` are updated to the matched values

---

### Requirement: Identifier cross-reference
The system SHALL maintain an `instrument_identifiers` table storing all known external identifiers for each instrument. Each row has: `instrument_id` (FK), `id_type` (`isin`, `cusip`, `figi`, `composite_figi`, `mic_code`, `coingecko_id`, `cmc_id`, `coincodex_id`, `contract_address`, `ticker_exchange`), `id_value`, and `chain` (for `contract_address` only).

#### Scenario: Multiple identifier types stored per instrument
- **WHEN** an instrument is enriched from multiple sources (e.g. EODHD provides ISIN, OpenFIGI provides FIGI)
- **THEN** both identifier rows are present in `instrument_identifiers` under the same `instrument_id`

#### Scenario: Contract address stored with chain
- **WHEN** a crypto token has a contract address on a specific blockchain
- **THEN** a row is stored with `id_type = 'contract_address'`, `id_value` = the address, and `chain` = the blockchain name (e.g. `ethereum`)

#### Scenario: Duplicate identifier rejected
- **WHEN** the same `(instrument_id, id_type, id_value)` triple is inserted twice
- **THEN** the second insert is silently ignored (upsert / `INSERT OR IGNORE`)

---

### Requirement: Symbol resolution
The system SHALL resolve a caller-supplied symbol string to a canonical `instrument_id` using a defined priority order: (1) exact `instrument_id`, (2) `ticker_exchange` identifier match, (3) loose `ticker` match scoped to a given `asset_class`.

#### Scenario: Resolution by instrument_id
- **WHEN** a caller provides a valid UUID that matches an `instrument_id`
- **THEN** that `instrument_id` is returned directly without further lookup

#### Scenario: Resolution by ticker and exchange
- **WHEN** a caller provides a symbol in `{TICKER}.{MIC}` format (e.g. `AAPL.XNAS`)
- **THEN** the system looks up `id_type = 'ticker_exchange'` in `instrument_identifiers` and returns the matching `instrument_id`

#### Scenario: Ambiguous ticker raises error
- **WHEN** a caller provides a bare ticker (e.g. `BTC`) without `asset_class` qualifier and multiple instruments match
- **THEN** the system returns a 400-level error listing the ambiguous matches

#### Scenario: Unknown symbol raises error
- **WHEN** a caller provides a symbol that matches no instrument by any resolution method
- **THEN** the system returns a 404-level error

---

### Requirement: Attribute source map
The system SHALL maintain an `attribute_source_map` table that records data provenance for individual instrument attributes. Each row stores: `instrument_id` (FK → instruments), `attribute_name` (VARCHAR, matching the canonical column name, e.g. `ticker`, `full_name`, `launch_date`), `data_source_id` (FK → data_source), `last_updated_at` (TIMESTAMPTZ). The primary key is `(instrument_id, attribute_name)`.

#### Scenario: Attribute provenance recorded during migration
- **WHEN** the migration endpoint promotes CoinMarketCap data for an instrument
- **THEN** one row per updated attribute is upserted into `attribute_source_map` with `data_source_id` pointing to the CoinMarketCap entry and `last_updated_at` set to the current UTC timestamp

#### Scenario: Provenance upserted on re-migration
- **WHEN** the migration endpoint is called a second time for the same instrument and attribute
- **THEN** the existing `attribute_source_map` row is updated (`last_updated_at` refreshed) rather than creating a duplicate

---

### Requirement: Ticker source map
The system SHALL maintain a `ticker_source_map` table to resolve ambiguous ticker symbols across data providers. Each row stores: `instrument_id` (FK → instruments), `data_source_id` (FK → data_source), `source_ticker` (VARCHAR — the ticker string as known to that provider), `is_canonical` (BOOLEAN, default FALSE). The primary key is `(instrument_id, data_source_id)`.

#### Scenario: Source ticker stored for CoinMarketCap instrument
- **WHEN** a crypto instrument is matched to a CoinMarketCap entry during migration
- **THEN** a row is upserted in `ticker_source_map` with the CoinMarketCap `symbol` as `source_ticker` and `data_source_id` pointing to the CoinMarketCap entry

#### Scenario: Canonical ticker flag
- **WHEN** `is_canonical = TRUE` on a `ticker_source_map` row
- **THEN** that row's `source_ticker` is preferred for display and resolution over rows where `is_canonical = FALSE`

#### Scenario: Ambiguous ticker across sources
- **WHEN** two different data sources provide different tickers for the same `instrument_id`
- **THEN** both rows coexist without conflict (each has a unique `(instrument_id, data_source_id)` key)
