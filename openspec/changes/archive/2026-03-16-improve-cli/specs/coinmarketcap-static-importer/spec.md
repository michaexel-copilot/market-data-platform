## MODIFIED Requirements

### Requirement: market-data import-cmc-static CLI sub-command
The `market-data import-cmc-static` sub-command SHALL delegate execution to
`POST /v1/admin/import-cmc-static` via HTTP instead of opening a DuckDB connection
directly. It SHALL accept:
- `dir` (positional, optional): path to pass as the `dir` field in the request body.
  If omitted, the server uses `CMC_STATIC_DIR`.
- `--dry-run` (flag): **removed**; the REST endpoint does not support dry-run mode.
- `--url` (optional): base URL for the REST service. Defaults to `MARKET_DATA_URL` env
  var, then `http://localhost:8010`.

On success the CLI SHALL print the returned counts to stdout. On HTTP error it SHALL
print the error message to stderr and exit with code 1.

#### Scenario: Successful import via CLI with no arguments
- **WHEN** `uv run market-data import-cmc-static` is executed and the server is running with `CMC_STATIC_DIR` set
- **THEN** the CLI calls `POST /v1/admin/import-cmc-static` with an empty body, prints the counts, and exits 0

#### Scenario: Successful import via CLI with explicit directory
- **WHEN** `uv run market-data import-cmc-static /data/cmc` is executed and the server is running
- **THEN** the CLI calls `POST /v1/admin/import-cmc-static` with body `{"dir": "/data/cmc"}`, prints the counts, and exits 0

#### Scenario: Server returns 422 for missing directory
- **WHEN** `uv run market-data import-cmc-static /nonexistent` is executed
- **THEN** the CLI prints the error from the response to stderr and exits with code 1

#### Scenario: Server not running
- **WHEN** `uv run market-data import-cmc-static` is executed and no server is listening
- **THEN** the CLI prints a connection error to stderr and exits with code 1
