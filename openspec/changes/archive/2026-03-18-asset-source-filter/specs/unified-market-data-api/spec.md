## MODIFIED Requirements

### Requirement: REST API — instruments endpoint
The system SHALL expose a REST endpoint `GET /v1/instruments` that returns a paginated list of
instruments. Query parameters SHALL include: `asset_class` (filter), `is_active` (filter,
default `true`), `q` (full-text search on `ticker` and `full_name`), `page` (default 1),
`page_size` (default 50, max 200), `tradeable_on` (optional, values: `hyperliquid`), `network`
(optional, values: `mainnet` | `testnet`, default `mainnet`, used only when `tradeable_on` is
set), and `sources` (optional, comma-separated list of data source short-names, e.g.
`eodhd,hl`). The response SHALL include `total`, `page`, `page_size`, and `items` fields. When
`tradeable_on=hyperliquid` is set, each item SHALL include an additional `hyperliquid` object
with `hl_symbol`, `lot_size`, `tick_size`, `max_leverage`, and `is_active` for the requested
network. When `sources` is provided, only instruments present in **all** specified sources
(i.e. the intersection) SHALL be returned.

#### Scenario: List active instruments
- **WHEN** `GET /v1/instruments?asset_class=crypto&is_active=true` is called
- **THEN** a paginated JSON response is returned containing only active crypto instruments

#### Scenario: Search by ticker
- **WHEN** `GET /v1/instruments?q=BTC` is called
- **THEN** instruments with `ticker` or `full_name` containing `BTC` are returned

#### Scenario: Single instrument by symbol
- **WHEN** `GET /v1/instruments/{symbol}` is called with a valid symbol (UUID, `TICKER.MIC`,
  or ticker)
- **THEN** a single instrument record is returned with all core fields and asset-class-specific
  attributes

#### Scenario: Unknown symbol returns 404
- **WHEN** `GET /v1/instruments/{symbol}` is called with an unknown symbol
- **THEN** HTTP 404 is returned with a JSON error body

#### Scenario: Filter by tradeable_on hyperliquid mainnet
- **WHEN** `GET /v1/instruments?tradeable_on=hyperliquid` is called (network defaults to
  `mainnet`)
- **THEN** only instruments with an active row in `instrument_hyperliquid` for
  `network='mainnet'` are returned, each with a `hyperliquid` object containing `hl_symbol`,
  `lot_size`, `tick_size`, and `max_leverage`

#### Scenario: Filter by tradeable_on hyperliquid testnet
- **WHEN** `GET /v1/instruments?tradeable_on=hyperliquid&network=testnet` is called
- **THEN** only instruments with an active row in `instrument_hyperliquid` for
  `network='testnet'` are returned, each with a `hyperliquid` object

#### Scenario: tradeable_on filter returns empty when no HL data imported
- **WHEN** `GET /v1/instruments?tradeable_on=hyperliquid` is called and
  `instrument_hyperliquid` is empty
- **THEN** a paginated response with `total=0` and `items=[]` is returned

#### Scenario: Invalid tradeable_on value returns 400
- **WHEN** `GET /v1/instruments?tradeable_on=unknown_exchange` is called
- **THEN** HTTP 400 is returned with a JSON error body listing valid values

#### Scenario: Filter by single source
- **WHEN** `GET /v1/instruments?sources=eodhd` is called
- **THEN** only instruments with a row `source_short_name = 'eodhd'` in
  `instrument_source_intersection` are returned

#### Scenario: Filter by intersection of two sources
- **WHEN** `GET /v1/instruments?sources=eodhd,hl` is called
- **THEN** only instruments present in **both** `eodhd` and `hl` in
  `instrument_source_intersection` are returned; instruments present in only one source are
  excluded

#### Scenario: sources omitted returns all instruments
- **WHEN** `GET /v1/instruments` is called without a `sources` parameter
- **THEN** the response is identical to the existing behaviour — no source filtering applied

#### Scenario: Unknown source short-name returns empty
- **WHEN** `GET /v1/instruments?sources=nonexistent` is called
- **THEN** a paginated response with `total=0` and `items=[]` is returned (no error)

#### Scenario: sources combined with asset_class filter
- **WHEN** `GET /v1/instruments?asset_class=crypto&sources=eodhd,hl` is called
- **THEN** only active crypto instruments present in both `eodhd` and `hl` sources are returned
