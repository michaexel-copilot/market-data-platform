# Compute Indicators REST

## Purpose

Defines the `POST /v1/admin/compute-indicators` REST endpoint that bulk-computes
strategy indicator values for one or all active instruments and persists them to the
`trading_strategies` table. This endpoint is the server-side counterpart to the
`compute-indicators` CLI.

## Requirements

### Requirement: POST /v1/admin/compute-indicators endpoint
The system SHALL provide a REST endpoint `POST /v1/admin/compute-indicators` that
accepts a JSON body and computes strategy indicators for one or all active instruments,
persisting results to the `trading_strategies` table. The accepted body fields are:
- `strategy` (string, required): name of the strategy to run (e.g. `best_sma`).
- `symbol` (string, optional): ticker symbol. If omitted, all active instruments are processed.
- `sl_short` (float, optional, default 10.0): stop-loss % for short.
- `sl_long` (float, optional, default 10.0): stop-loss % for long.
- `pos_usd` (float, optional, default 100.0): position size in USD.

The endpoint SHALL return HTTP 200 with a JSON body:
```json
{
  "ok": <int>,
  "errors": <int>,
  "results": [
    {"ticker": "<symbol>", "status": "ok", "elapsed_s": <float>},
    {"ticker": "<symbol>", "status": "error", "error": "<message>", "elapsed_s": <float>}
  ]
}
```

#### Scenario: Bulk run for all active instruments succeeds
- **WHEN** `POST /v1/admin/compute-indicators` is called with body `{"strategy": "best_sma"}`
- **THEN** the response is HTTP 200 with `ok` equal to the number of active instruments and `errors` equal to 0

#### Scenario: Single symbol run
- **WHEN** `POST /v1/admin/compute-indicators` is called with body `{"strategy": "best_sma", "symbol": "BTC"}`
- **THEN** only the BTC instrument is processed and `results` contains exactly one entry

#### Scenario: Unknown strategy rejected
- **WHEN** `POST /v1/admin/compute-indicators` is called with an unknown strategy name
- **THEN** the response is HTTP 422 with `{"detail": "Unknown strategy '...'. Available: ..."}`

#### Scenario: Unknown symbol rejected
- **WHEN** `POST /v1/admin/compute-indicators` is called with a symbol that does not exist
- **THEN** the response is HTTP 404

#### Scenario: Per-instrument errors do not abort the run
- **WHEN** one instrument raises a computation error during a bulk run
- **THEN** the endpoint continues processing remaining instruments and the failed instrument appears in `results` with `"status": "error"`; the response is still HTTP 200

#### Scenario: Partial failure reflected in response counts
- **WHEN** 3 instruments succeed and 1 fails
- **THEN** the response contains `"ok": 3` and `"errors": 1`
