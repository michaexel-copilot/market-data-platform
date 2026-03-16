## Why

When the REST service is running, any CLI command that opens a second DuckDB connection
fails with "database is locked" because DuckDB only allows one writer at a time.
The CLIs bypass the API layer and go directly to the database, making it impossible to
use them alongside the running service — the primary production scenario.

## What Changes

- Add a `POST /v1/admin/compute-indicators` REST endpoint that runs the bulk indicator
  computation job (all active instruments or a specific symbol) with the same parameters
  as the existing CLI.
- Add a `POST /v1/admin/import-cmc-static` REST endpoint that triggers the CoinMarketCap
  static TSV import from the server-side `CMC_STATIC_DIR` path.
- Change `compute-indicators` CLI to call `POST /v1/admin/compute-indicators` via HTTP
  instead of opening its own DuckDB connection.
- Change `market-data import-cmc-static` CLI to call `POST /v1/admin/import-cmc-static`
  via HTTP instead of opening its own DuckDB connection.
- Document all admin REST endpoints and their corresponding CLI invocations with
  request/response examples in the existing `docs/management-console.md`.
- The CLIs SHALL read the base URL from the environment variable `MARKET_DATA_URL`
  (default: `http://localhost:8010`) so they work against any deployment.

## Capabilities

### New Capabilities

- `compute-indicators-rest`: REST endpoint `POST /v1/admin/compute-indicators` — accepts
  `strategy`, optional `symbol`, `sl_short`, `sl_long`, `pos_usd`; returns per-instrument
  results (ok / error counts).
- `import-cmc-static-rest`: REST endpoint `POST /v1/admin/import-cmc-static` — accepts
  optional `dir` body field (falls back to `CMC_STATIC_DIR` env var on the server);
  returns import counts.

### Modified Capabilities

- `compute-indicators-cli`: CLI now delegates to `POST /v1/admin/compute-indicators`
  instead of connecting to DuckDB directly.  Behavior and exit codes are preserved.
- `coinmarketcap-static-importer`: `market-data import-cmc-static` CLI now delegates to
  `POST /v1/admin/import-cmc-static` instead of connecting to DuckDB directly.

## Impact

- `src/market_data/api/rest/admin.py` — two new route handlers
- `src/market_data/cli/compute_indicators.py` — rewrite to HTTP client
- `src/market_data/cli/__init__.py` (`import-cmc-static` sub-command) — rewrite to HTTP client
- `tests/test_cli_compute_indicators.py` — update tests
- `docs/management-console.md` — add endpoint + CLI reference section
- No schema changes; no breaking changes to existing endpoints
