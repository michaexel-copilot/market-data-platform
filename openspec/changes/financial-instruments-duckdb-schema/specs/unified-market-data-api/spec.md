## ADDED Requirements

### Requirement: REST API — instruments endpoint
The system SHALL expose a REST endpoint `GET /v1/instruments` that returns a paginated list of instruments. Query parameters SHALL include: `asset_class` (filter), `is_active` (filter, default `true`), `q` (full-text search on `ticker` and `full_name`), `page` (default 1), `page_size` (default 50, max 200). The response SHALL include `total`, `page`, `page_size`, and `items` fields.

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

---

### Requirement: REST API — OHLCV endpoint
The system SHALL expose a REST endpoint `GET /v1/ohlcv/{symbol}` for time-series data. Query parameters SHALL include: `interval` (required: `1m`, `5m`, `1h`, `1d`, `1w`, `1mo`), `since` (ISO 8601 datetime, optional), `until` (ISO 8601 datetime, optional), `page` / `page_size` (default page_size 1000, max 5000). Results SHALL be sorted by `ts` ascending.

#### Scenario: Daily OHLCV for equity
- **WHEN** `GET /v1/ohlcv/AAPL.XNAS?interval=1d&since=2025-01-01&until=2025-12-31` is called
- **THEN** up to 252 daily candles are returned for AAPL on XNAS within the date range

#### Scenario: Weekly derived data
- **WHEN** `GET /v1/ohlcv/BTC.crypto?interval=1w` is called
- **THEN** weekly aggregated candles derived from `ohlcv_weekly` view are returned

#### Scenario: Invalid interval returns 400
- **WHEN** `GET /v1/ohlcv/BTC?interval=15m` is called
- **THEN** HTTP 400 is returned with an error message listing valid intervals

#### Scenario: Pagination for large result sets
- **WHEN** `GET /v1/ohlcv/BTC?interval=1m&since=2026-01-01` returns more than `page_size` rows
- **THEN** the response includes a `next_page` cursor or `page` token for fetching subsequent pages

---

### Requirement: REST API — fundamentals endpoint
The system SHALL expose `GET /v1/instruments/{symbol}/fundamentals` returning asset-class-specific fundamental data. For crypto: supply fields, blockchain info. For equities: shares outstanding, float, SIC code, country. For ETFs: tracking index, expense ratio, AUM.

#### Scenario: Crypto fundamentals
- **WHEN** `GET /v1/instruments/BTC/fundamentals` is called
- **THEN** a JSON response is returned with `total_supply`, `max_supply`, `circulating_supply`, `blockchain_network`, `consensus_mechanism`

#### Scenario: Equity fundamentals
- **WHEN** `GET /v1/instruments/AAPL.XNAS/fundamentals` is called
- **THEN** a JSON response is returned with `shares_outstanding`, `float_shares`, `sic_code`, `country_of_incorporation`, `isin`, `figi`

#### Scenario: No fundamentals available returns 404
- **WHEN** `GET /v1/instruments/{symbol}/fundamentals` is called for an instrument with no asset-class record
- **THEN** HTTP 404 is returned

---

### Requirement: JSON-RPC interface
The system SHALL expose a JSON-RPC 2.0 endpoint at `POST /jsonrpc`. It SHALL implement the following methods mirroring the REST API: `instruments.list`, `instruments.get`, `ohlcv.get`, `instruments.fundamentals`. Request/response payloads SHALL follow the JSON-RPC 2.0 spec (with `jsonrpc`, `method`, `params`, `id` fields).

#### Scenario: JSON-RPC instruments.list call
- **WHEN** a POST to `/jsonrpc` with body `{"jsonrpc":"2.0","method":"instruments.list","params":{"asset_class":"crypto"},"id":1}` is made
- **THEN** a JSON-RPC 2.0 response is returned with `result` containing the same paginated instrument list as the REST equivalent

#### Scenario: JSON-RPC method not found
- **WHEN** a POST to `/jsonrpc` with an unknown `method` is made
- **THEN** a JSON-RPC 2.0 error response is returned with `code: -32601` (Method not found)

#### Scenario: JSON-RPC batch request
- **WHEN** a POST to `/jsonrpc` with a JSON array of multiple request objects is made
- **THEN** a JSON array of corresponding response objects is returned

---

### Requirement: gRPC interface
The system SHALL expose a gRPC service on port 50051. The proto definition SHALL define a `MarketDataService` with RPCs: `ListInstruments`, `GetInstrument`, `GetOHLCV` (server-streaming), `GetFundamentals`. Proto files SHALL be versioned in `proto/v1/`.

#### Scenario: gRPC GetOHLCV streaming
- **WHEN** a gRPC `GetOHLCV` call is made with a valid symbol and interval
- **THEN** the server streams `OHLCVBar` messages to the client, one per candle, in ascending timestamp order

#### Scenario: gRPC unavailable symbol
- **WHEN** a gRPC `GetInstrument` call is made with an unknown symbol
- **THEN** the server returns a gRPC `NOT_FOUND` status code

#### Scenario: gRPC service reflects REST data
- **WHEN** identical queries are made via REST `GET /v1/ohlcv/{symbol}` and gRPC `GetOHLCV`
- **THEN** both return the same underlying data

---

### Requirement: Consistent error responses
All three API surfaces (REST, JSON-RPC, gRPC) SHALL return structured errors. REST SHALL use JSON `{"error": {"code": <string>, "message": <string>}}` bodies. JSON-RPC SHALL follow the JSON-RPC 2.0 error spec. gRPC SHALL use standard gRPC status codes with a detail message.

#### Scenario: Validation error on REST
- **WHEN** a REST request is made with an invalid parameter (e.g. malformed date)
- **THEN** HTTP 422 is returned with a JSON body identifying the invalid field and reason

#### Scenario: Internal error not leaked
- **WHEN** an unexpected internal error occurs during request handling
- **THEN** REST returns HTTP 500 with a generic error message; the internal exception detail is logged but NOT exposed in the response

---

### Requirement: API runs via uv
The system SHALL be startable with `uv run serve`. The `serve` script SHALL start both the FastAPI/uvicorn server (port 8000) and the gRPC server (port 50051) in the same process using `asyncio.gather`.

#### Scenario: Service starts with uv run serve
- **WHEN** `uv run serve` is executed in the project root
- **THEN** both the HTTP server on port 8000 and gRPC server on port 50051 become ready to accept connections

#### Scenario: uv run serve without virtualenv activation
- **WHEN** `uv run serve` is executed without manually activating a virtualenv
- **THEN** uv resolves the environment from `pyproject.toml` / `uv.lock` and the service starts successfully
