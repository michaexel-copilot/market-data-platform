# Data Source Registry

## Purpose

Defines the registry of known data providers, their metadata, and priority ordering for data retrieval operations.

## Requirements

### Requirement: Data source registry
The system SHALL maintain a `data_source` table that stores one row per known data provider with the following columns: `data_source_id` (auto-increment integer, primary key), `name` (VARCHAR, e.g. `CoinMarketCap`), `short_name` (VARCHAR, e.g. `cmc`), `base_url` (VARCHAR, e.g. `https://coinmarketcap.com`), `api_page_url` (VARCHAR, nullable), `retrieval_priority` (INTEGER, nullable; 0 = highest priority; NULL = source is disabled).

#### Scenario: Data source created
- **WHEN** a new data source row is inserted with name `CoinMarketCap`, short name `cmc`, base URL `https://coinmarketcap.com`, and priority `0`
- **THEN** a row exists in `data_source` with those values and a generated `data_source_id`

#### Scenario: Disabled data source
- **WHEN** a data source row has `retrieval_priority = NULL`
- **THEN** it is excluded from any priority-ordered queries for active sources

#### Scenario: Priority ordering
- **WHEN** multiple data sources are active (non-NULL priority)
- **THEN** a query ordering by `retrieval_priority ASC` returns rows from lowest integer value first (0 = highest priority)
