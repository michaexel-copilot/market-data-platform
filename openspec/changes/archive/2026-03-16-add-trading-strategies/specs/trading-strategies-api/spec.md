# Trading Strategies API

## Purpose

Defines the REST endpoints for reading precomputed strategy indicator values and triggering single-instrument computation.

## ADDED Requirements

### Requirement: GET /v1/trading-strategies/{symbol}
The system SHALL provide `GET /v1/trading-strategies/{symbol}` that returns all precomputed indicators for the resolved instrument. An optional query parameter `strategy_name` filters results to a single strategy. The response SHALL be a JSON object with a `items` array.

Each item SHALL contain: `strategy_name` (string), `indicator_name` (string), `indicator_value` (number), `parameters` (object or null), `computed_at` (ISO 8601 UTC string).

#### Scenario: Indicators exist for symbol
- **WHEN** `GET /v1/trading-strategies/BTC` is requested and the database contains rows for BTC
- **THEN** the response is HTTP 200 with a JSON body `{"items": [...]}` listing all indicator rows for BTC

#### Scenario: Filtered by strategy_name
- **WHEN** `GET /v1/trading-strategies/BTC?strategy_name=best_sma` is requested
- **THEN** the response contains only rows where `strategy_name = "best_sma"`

#### Scenario: No precomputed data for symbol
- **WHEN** `GET /v1/trading-strategies/BTC` is requested and no rows exist for BTC in `trading_strategies`
- **THEN** the response is HTTP 404 with a JSON body `{"error": "No precomputed indicators for BTC. Run compute-indicators --strategy <name> first."}`

#### Scenario: Symbol not found in instrument registry
- **WHEN** `GET /v1/trading-strategies/UNKNOWN_TICKER` is requested and the symbol cannot be resolved
- **THEN** the response is HTTP 404 with the standard instrument-not-found error

---

### Requirement: POST /v1/trading-strategies/{symbol}/compute
The system SHALL provide `POST /v1/trading-strategies/{symbol}/compute` that synchronously runs a strategy computation for the resolved instrument and stores the results. The request body SHALL accept `strategy` (string, required), `sl_short` (number, default 10), `sl_long` (number, default 10), `pos_usd` (number, default 100).

#### Scenario: Successful compute
- **WHEN** `POST /v1/trading-strategies/BTC/compute` with body `{"strategy": "best_sma"}` is requested and OHLCV data exists
- **THEN** the response is HTTP 200 with a JSON body `{"computed": [{"indicator_name": "sma_low", "indicator_value": 7}, {"indicator_name": "sma_high", "indicator_value": 21}]}` and the values are persisted to `trading_strategies`

#### Scenario: No OHLCV data for symbol
- **WHEN** `POST /v1/trading-strategies/BTC/compute` is requested but the instrument has no `1d` OHLCV rows in the database
- **THEN** the response is HTTP 422 with a JSON body `{"error": "No OHLCV data available for BTC. Ingest daily candles first."}`

#### Scenario: Unknown strategy in compute request
- **WHEN** `POST /v1/trading-strategies/BTC/compute` with body `{"strategy": "unknown"}` is requested
- **THEN** the response is HTTP 422 with a JSON body `{"error": "Unknown strategy 'unknown'. Available: best_sma"}`

#### Scenario: Symbol not found in instrument registry
- **WHEN** `POST /v1/trading-strategies/UNKNOWN/compute` is requested
- **THEN** the response is HTTP 404 with the standard instrument-not-found error
