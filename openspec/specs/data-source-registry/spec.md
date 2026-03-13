# Data Source Registry

## Purpose

Defines the registry of known data providers, their metadata, and priority ordering for data retrieval operations.

## Requirements

### Requirement: Data source registry
The system SHALL maintain a `data_source` table that stores one row per known data provider with the following columns: `data_source_id` (auto-increment integer, primary key), `name` (VARCHAR, e.g. `CoinMarketCap`), `short_name` (VARCHAR, e.g. `cmc`), `base_url` (VARCHAR, e.g. `https://coinmarketcap.com`), `api_page_url` (VARCHAR, nullable), `retrieval_priority` (INTEGER, nullable; 0 = highest priority; NULL = source is disabled). The table SHALL be pre-seeded with CoinMarketCap (id=1, priority=0) and EOD Historical Data / eodhd (id=2, priority=1).

#### Scenario: Data source created
- **WHEN** a new data source row is inserted with name `CoinMarketCap`, short name `cmc`, base URL `https://coinmarketcap.com`, and priority `0`
- **THEN** a row exists in `data_source` with those values and a generated `data_source_id`

#### Scenario: Disabled data source
- **WHEN** a data source row has `retrieval_priority = NULL`
- **THEN** it is excluded from any priority-ordered queries for active sources

#### Scenario: Priority ordering
- **WHEN** multiple data sources are active (non-NULL priority)
- **THEN** a query ordering by `retrieval_priority ASC` returns rows from lowest integer value first (0 = highest priority)

#### Scenario: eodhd data source exists
- **WHEN** the database migrations have been applied
- **THEN** a row exists in `data_source` with `short_name = 'eodhd'`, `base_url = 'https://eodhd.com'`, and `retrieval_priority = 1`

---

### Requirement: OHLCV data availability registry
The system SHALL maintain an `ohlcv_data_available` table recording which native OHLCV intervals each data source covers per instrument. Columns: `instrument_id` (VARCHAR, FK → `instruments`), `data_source_id` (INTEGER, FK → `data_source`), `has_1m` (BOOLEAN DEFAULT FALSE), `has_5m` (BOOLEAN DEFAULT FALSE), `has_1h` (BOOLEAN DEFAULT FALSE), `has_1d` (BOOLEAN DEFAULT FALSE). Primary key: `(instrument_id, data_source_id)`.

#### Scenario: CMC availability seeded
- **WHEN** migrations are applied after CMC instruments exist
- **THEN** each crypto instrument has a row in `ohlcv_data_available` for data_source_id=1 (cmc) with `has_1d=true` and all other interval flags false

#### Scenario: eodhd availability seeded
- **WHEN** migrations are applied after eodhd data source is seeded
- **THEN** each crypto instrument has a row in `ohlcv_data_available` for the eodhd data source with `has_1m=true`, `has_5m=true`, `has_1h=true`, `has_1d=true`

#### Scenario: Idempotent seeding
- **WHEN** migrations are applied more than once
- **THEN** no duplicate rows are created in `ohlcv_data_available`
