## ADDED Requirements

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
