# Data Source Connectors

## Purpose

Defines the connector protocol, rate limiting, field normalisation, registry, and supported provider implementations for fetching market data from external sources into the platform.

## Requirements

### Requirement: Connector protocol interface
The system SHALL define a `Connector` Protocol with the following async methods: `fetch_ohlcv(instrument_id, interval, since, until) -> list[OHLCVRecord]`, `fetch_instruments(asset_class) -> list[InstrumentRecord]`, and optionally `fetch_fundamentals(instrument_id) -> FundamentalsRecord | None`. Each connector SHALL declare `name: str`, `supported_asset_classes: list[AssetClass]`, and `supported_intervals: list[Interval]` as class-level attributes.

#### Scenario: Connector satisfies protocol
- **WHEN** a new connector module implements all required methods and attributes matching the Protocol signature
- **THEN** it is accepted by the ingestion engine without any import of a base class

#### Scenario: Connector missing required method
- **WHEN** a connector module does not implement `fetch_ohlcv`
- **THEN** a `TypeError` is raised at the point of use (protocol violation, caught at runtime by type checker or explicit `isinstance` check)

---

### Requirement: Per-connector rate limiting
Each connector SHALL implement rate limiting appropriate to its provider's published limits. Rate limiting SHALL use an asyncio token-bucket mechanism. When the rate limit is reached, the connector SHALL wait (backpressure) rather than raise an error.

#### Scenario: Rate limit respected
- **WHEN** a connector exhausts its token bucket
- **THEN** subsequent requests are delayed until tokens replenish; no `429` errors are raised to the ingestion engine

#### Scenario: Provider returns 429
- **WHEN** a provider returns HTTP 429 despite rate limiting
- **THEN** the connector applies exponential backoff (starting at 5s, max 5 retries) before retrying

---

### Requirement: Field mapping and normalisation
Each connector SHALL map provider-native field names to the platform's canonical `OHLCVRecord` and `InstrumentRecord` schemas. All timestamps SHALL be normalised to UTC TIMESTAMPTZ. All prices SHALL be stored as DOUBLE (no string prices). Missing optional fields SHALL be set to `None`.

#### Scenario: Provider returns local-timezone timestamps
- **WHEN** a provider returns timestamps with a non-UTC timezone offset
- **THEN** the connector converts them to UTC before returning records

#### Scenario: Provider returns string prices
- **WHEN** a provider returns prices as strings (e.g. `"42000.50"`)
- **THEN** the connector casts them to `float` before populating `OHLCVRecord`

---

### Requirement: Connector registry and auto-discovery
The system SHALL automatically discover and register all connector modules present in the `market_data/connectors/` package. Each connector module SHALL expose a module-level `connector` object satisfying the `Connector` protocol. The registry SHALL be queryable by `name`, `asset_class`, and `interval`.

#### Scenario: New connector added
- **WHEN** a new Python module is added to `market_data/connectors/` with a valid `connector` object
- **THEN** the connector is available to the ingestion engine without any changes to configuration files

#### Scenario: Registry query by asset class
- **WHEN** the ingestion engine queries the registry for connectors supporting `asset_class = 'crypto'`
- **THEN** only connectors with `'crypto'` in `supported_asset_classes` are returned

---

### Requirement: Supported connectors
The system SHALL provide connector implementations for the following providers: CoinGecko, CoinCodex, CoinMarketCap, EODHD, Yahoo Finance (`yfinance`), Polygon.io, Alpha Vantage, Tiingo, Financial Modeling Prep, Binance (public API), Kraken, OpenFIGI (reference only), SEC EDGAR (fundamentals only), Nasdaq Data Link.

#### Scenario: CoinGecko connector fetches crypto OHLCV
- **WHEN** `fetch_ohlcv` is called on the CoinGecko connector with `interval='1d'` and a valid crypto `instrument_id`
- **THEN** a list of `OHLCVRecord` objects is returned with fields mapped from CoinGecko's `/coins/{id}/ohlc` response

#### Scenario: EODHD connector fetches intraday equities
- **WHEN** `fetch_ohlcv` is called on the EODHD connector with `interval='1m'` and a valid equity `instrument_id`
- **THEN** a list of `OHLCVRecord` objects is returned using the EODHD intraday endpoint

#### Scenario: OpenFIGI connector used for reference only
- **WHEN** `fetch_instruments` is called on the OpenFIGI connector
- **THEN** it returns `InstrumentRecord` objects enriched with FIGI and composite FIGI identifiers; `fetch_ohlcv` is NOT implemented and SHALL raise `NotImplementedError`

#### Scenario: Binance connector requires no API key
- **WHEN** the Binance connector is initialised without an API key
- **THEN** it successfully fetches public OHLCV data from the Binance public REST API

---

### Requirement: Deduplication on write
The ingestion engine SHALL deduplicate records before writing to DuckDB. A record is a duplicate if `(instrument_id, interval, ts)` already exists in `ohlcv`. Duplicates SHALL be upserted (`INSERT OR REPLACE`), not silently dropped, to allow source corrections.

#### Scenario: Ingestion run with all-new data
- **WHEN** an ingestion run produces candles for timestamps not yet in the DB
- **THEN** all candles are inserted as new rows

#### Scenario: Re-ingestion of existing candles
- **WHEN** an ingestion run produces candles for timestamps already in the DB (e.g. a correction run)
- **THEN** existing rows are replaced with updated values

---

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
