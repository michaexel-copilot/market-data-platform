## ADDED Requirements

### Requirement: Static-file ingestion path
The system SHALL support a supplementary static-file ingestion path for CoinMarketCap data
that operates independently of the live API connector.  This path reads pre-downloaded TSV
snapshot files and loads them into dedicated DuckDB tables.  It SHALL NOT conflict with or
replace the live `CoinMarketCapConnector`.

#### Scenario: Static importer runs alongside live connector
- **WHEN** both the CMC static importer and the live `CoinMarketCapConnector` are active
- **THEN** they write to non-overlapping tables; neither overwrites the other's data

#### Scenario: Static importer available without API key
- **WHEN** the `CMC_API_KEY` environment variable is not set
- **THEN** the static importer still runs successfully using only the local TSV files
