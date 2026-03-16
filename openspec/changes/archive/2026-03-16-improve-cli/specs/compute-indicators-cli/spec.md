## MODIFIED Requirements

### Requirement: compute-indicators entry point
The system SHALL provide a CLI entry point `compute-indicators` (registered in
`pyproject.toml`) that accepts the following arguments:
- `--strategy` (required): name of the strategy to run (e.g. `best_sma`).
- `--symbol` (optional): ticker symbol to process. If omitted, all active instruments are processed.
- `--sl-short` (optional, default 10): stop-loss percentage for the short strategy.
- `--sl-long` (optional, default 10): stop-loss percentage for the long strategy.
- `--pos-usd` (optional, default 100): position size in USD.
- `--url` (optional): base URL for the REST service. Defaults to the value of `MARKET_DATA_URL` env var, then `http://localhost:8010`.

The CLI SHALL delegate execution to `POST /v1/admin/compute-indicators` via HTTP
instead of opening a DuckDB connection directly. Per-instrument results SHALL be
printed to stdout as before. The CLI SHALL exit 1 if the HTTP call fails or if the
response contains `errors > 0`.

#### Scenario: CLI invoked for all instruments
- **WHEN** `uv run compute-indicators --strategy best_sma` is executed
- **THEN** the command calls `POST /v1/admin/compute-indicators` with `{"strategy": "best_sma"}` and prints per-instrument results from the response

#### Scenario: CLI invoked for a single symbol
- **WHEN** `uv run compute-indicators --strategy best_sma --symbol BTC` is executed
- **THEN** the command calls `POST /v1/admin/compute-indicators` with `{"strategy": "best_sma", "symbol": "BTC"}` and prints the single result

#### Scenario: Unknown strategy name
- **WHEN** `uv run compute-indicators --strategy unknown_strategy` is executed
- **THEN** the server returns HTTP 422 and the CLI exits with a non-zero exit code and prints an error

#### Scenario: Server not running
- **WHEN** `uv run compute-indicators --strategy best_sma` is executed and no server is listening at the configured URL
- **THEN** the CLI prints a helpful connection error message to stderr and exits with code 1

### Requirement: Per-instrument error handling
The CLI SHALL reflect the error counts returned by the API. Each failure SHALL be
printed to stderr with the instrument ticker and error message. The CLI SHALL exit with
exit code 1 if `errors > 0`, exit code 0 if `errors == 0`.

#### Scenario: Instrument has no OHLCV data
- **WHEN** the CLI processes a response where one instrument has `"status": "error"`
- **THEN** the CLI prints the error to stderr and continues printing remaining results

#### Scenario: All instruments succeed
- **WHEN** the response contains `"errors": 0`
- **THEN** the process exits with code 0

#### Scenario: At least one instrument fails
- **WHEN** the response contains `"errors": 1` or more
- **THEN** the process exits with code 1
