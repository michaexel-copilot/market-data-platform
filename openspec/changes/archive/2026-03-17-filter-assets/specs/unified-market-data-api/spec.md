## MODIFIED Requirements

### Requirement: REST API — instruments endpoint
The system SHALL expose a REST endpoint `GET /v1/instruments` that returns a paginated list of instruments. Query parameters SHALL include: `asset_class` (filter), `is_active` (filter, default `true`), `q` (full-text search on `ticker` and `full_name`), `page` (default 1), `page_size` (default 50, max 200), `tradeable_on` (optional, values: `hyperliquid`), `network` (optional, values: `mainnet` | `testnet`, default `mainnet`, used only when `tradeable_on` is set). The response SHALL include `total`, `page`, `page_size`, and `items` fields. When `tradeable_on=hyperliquid` is set, each item SHALL include an additional `hyperliquid` object with `hl_symbol`, `lot_size`, `tick_size`, `max_leverage`, and `is_active` for the requested network.

#### Scenario: List active instruments
- **WHEN** `GET /v1/instruments?asset_class=crypto&is_active=true` is called
- **THEN** a paginated JSON response is returned containing only active crypto instruments

#### Scenario: Search by ticker
- **WHEN** `GET /v1/instruments?q=BTC` is called
- **THEN** instruments with `ticker` or `full_name` containing `BTC` are returned

#### Scenario: Single instrument by symbol
- **WHEN** `GET /v1/instruments/{symbol}` is called with a valid symbol (UUID, `TICKER.MIC`, or ticker)
- **THEN** a single instrument record is returned with all core fields and asset-class-specific attributes

#### Scenario: Unknown symbol returns 404
- **WHEN** `GET /v1/instruments/{symbol}` is called with an unknown symbol
- **THEN** HTTP 404 is returned with a JSON error body

#### Scenario: Filter by tradeable_on hyperliquid mainnet
- **WHEN** `GET /v1/instruments?tradeable_on=hyperliquid` is called (network defaults to `mainnet`)
- **THEN** only instruments with an active row in `instrument_hyperliquid` for `network='mainnet'` are returned, each with a `hyperliquid` object containing `hl_symbol`, `lot_size`, `tick_size`, and `max_leverage`

#### Scenario: Filter by tradeable_on hyperliquid testnet
- **WHEN** `GET /v1/instruments?tradeable_on=hyperliquid&network=testnet` is called
- **THEN** only instruments with an active row in `instrument_hyperliquid` for `network='testnet'` are returned, each with a `hyperliquid` object

#### Scenario: tradeable_on filter returns empty when no HL data imported
- **WHEN** `GET /v1/instruments?tradeable_on=hyperliquid` is called and `instrument_hyperliquid` is empty
- **THEN** a paginated response with `total=0` and `items=[]` is returned

#### Scenario: Invalid tradeable_on value returns 400
- **WHEN** `GET /v1/instruments?tradeable_on=unknown_exchange` is called
- **THEN** HTTP 400 is returned with a JSON error body listing valid values

---

## ADDED Requirements

### Requirement: REST API — import-hl-pairs admin endpoint
The system SHALL expose a REST endpoint `POST /v1/admin/import-hl-pairs` that accepts `{"network": "mainnet" | "testnet"}` and triggers the Hyperliquid connector to fetch pairs, reconcile against the instrument registry, and upsert into `instrument_hyperliquid`. The response SHALL return `{"upserted": N, "unmatched": M, "deactivated": K}`.

#### Scenario: Successful mainnet import
- **WHEN** `POST /v1/admin/import-hl-pairs` is called with `{"network": "mainnet"}`
- **THEN** pairs are fetched from the HL mainnet API, reconciled, upserted, and the response contains counts for `upserted`, `unmatched`, and `deactivated`

#### Scenario: Zero pairs warning
- **WHEN** the HL API returns an empty list
- **THEN** the response returns `{"upserted": 0, "unmatched": 0, "deactivated": K}` where `K` is the number of previously active rows now deactivated

#### Scenario: Invalid network returns 422
- **WHEN** `POST /v1/admin/import-hl-pairs` is called with `{"network": "invalid"}`
- **THEN** HTTP 422 is returned with a validation error

---

### Requirement: CLI — import-hl-pairs command
The system SHALL provide a CLI command `market-data import-hl-pairs` with a `--network` flag (`mainnet` or `testnet`, default `mainnet`) that calls `POST /v1/admin/import-hl-pairs` and prints the result summary to stdout.

#### Scenario: Successful CLI import
- **WHEN** `market-data import-hl-pairs --network mainnet` is run
- **THEN** the command prints a summary line such as `Imported 142 pairs (3 unmatched, 0 deactivated)` and exits with code 0

#### Scenario: CLI handles server error
- **WHEN** the API server is unreachable
- **THEN** an error message is printed to stderr and the command exits with code 1
