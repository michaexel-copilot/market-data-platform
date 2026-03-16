# import-ohlcv CLI

## Purpose

Provides the `import-ohlcv` CLI command and the backing `POST /v1/admin/import-ohlcv` REST endpoint for bulk-importing hourly OHLCV data from the local eodhd file cache into the database. This is a prerequisite step before running `compute-indicators`.

## Requirements

### Requirement: import-ohlcv CLI entry point
The system SHALL provide a `import-ohlcv` CLI command (registered as `uv run import-ohlcv`) that imports OHLCV data from the local eodhd cache into the database.

The CLI SHALL accept:
- `--interval` (required): OHLCV interval to import (e.g. `1h`)
- `--symbol` (optional): Ticker to restrict import to a single instrument. If omitted, all active instruments are processed.
- `--url` (optional): Override the REST service base URL (default: `$MARKET_DATA_URL` or `http://localhost:8010`).

The CLI SHALL POST to `POST /v1/admin/import-ohlcv` and print per-ticker status lines in the same format as `compute-indicators`.

#### Scenario: All instruments imported successfully
- **WHEN** `uv run import-ohlcv --interval 1h` is invoked and the server processes all instruments without error
- **THEN** each ticker line is printed as `<TICKER>   OK  (<elapsed>s)` and the process exits with code 0

#### Scenario: Some instruments fail
- **WHEN** one or more tickers fail during import
- **THEN** the failing tickers are printed as `<TICKER>   ERROR: <message>  (<elapsed>s)` and the process exits with code 1

#### Scenario: Single instrument import
- **WHEN** `uv run import-ohlcv --interval 1h --symbol BTC` is invoked
- **THEN** only the BTC instrument is imported

#### Scenario: Unknown interval rejected
- **WHEN** `--interval` is a value not supported by the cache importer (e.g. `2h`)
- **THEN** the server returns HTTP 422 and the CLI prints the error and exits with code 1

---

### Requirement: POST /v1/admin/import-ohlcv endpoint
The system SHALL expose a `POST /v1/admin/import-ohlcv` REST endpoint under the admin router.

The request body SHALL accept:
- `interval` (required, string): OHLCV interval (must be a supported native interval).
- `symbol` (optional, string): Restrict import to a single ticker.

The response SHALL be `{ok: int, errors: int, results: [{ticker, status, rows_imported?, elapsed_s, error?}]}`.

For each instrument processed, the endpoint SHALL call the existing `import_from_cache` function with `source_short_name = "eodhd"`.

If `symbol` is provided and not found in the instruments table, the endpoint SHALL return HTTP 404.

#### Scenario: Bulk import succeeds
- **WHEN** `POST /v1/admin/import-ohlcv` is called with `{"interval": "1h"}` and all active instruments have matching files
- **THEN** the response contains `{ok: N, errors: 0, results: [...]}` with one entry per instrument

#### Scenario: Instrument with no matching file
- **WHEN** an active instrument has no file in the eodhd 1-hour folder matching its `instrument_id` or `ticker`
- **THEN** that instrument's result has `status: "folder_not_found"` or `rows_imported: 0` and counts towards `errors`

#### Scenario: Single symbol import
- **WHEN** `POST /v1/admin/import-ohlcv` is called with `{"interval": "1h", "symbol": "BTC"}`
- **THEN** only the BTC instrument is processed and the response contains exactly one result entry

#### Scenario: Unknown symbol returns 404
- **WHEN** `POST /v1/admin/import-ohlcv` is called with `{"symbol": "DOESNOTEXIST", "interval": "1h"}`
- **THEN** the response is HTTP 404 with a detail message
