# Compute Indicators CLI

## Purpose

Defines the `compute-indicators` CLI command that bulk-computes strategy indicator values for all active instruments (or a specific symbol) and persists them to the `trading_strategies` table.

## ADDED Requirements

### Requirement: compute-indicators entry point
The system SHALL provide a CLI entry point `compute-indicators` (registered in `pyproject.toml`) that accepts the following arguments:
- `--strategy` (required): name of the strategy to run (e.g. `best_sma`).
- `--symbol` (optional): ticker symbol to process. If omitted, all active instruments in the `instruments` table are processed.
- `--sl-short` (optional, default 10): stop-loss percentage for the short strategy.
- `--sl-long` (optional, default 10): stop-loss percentage for the long strategy.
- `--pos-usd` (optional, default 100): position size in USD.

#### Scenario: CLI invoked for all instruments
- **WHEN** `uv run compute-indicators --strategy best_sma` is executed
- **THEN** the command iterates all active instruments in the database and attempts to compute the strategy for each

#### Scenario: CLI invoked for a single symbol
- **WHEN** `uv run compute-indicators --strategy best_sma --symbol BTC` is executed
- **THEN** the command resolves `BTC` to its `instrument_id` and computes only that instrument

#### Scenario: Unknown strategy name
- **WHEN** `uv run compute-indicators --strategy unknown_strategy` is executed
- **THEN** the command exits with a non-zero exit code and prints an error listing available strategy names

---

### Requirement: Per-instrument error handling
The CLI SHALL skip instruments that fail computation (e.g. due to missing OHLCV data) and continue processing remaining instruments. Each failure SHALL be logged to stderr with the instrument ticker and the error message. The CLI SHALL exit with exit code 1 if any instrument failed, exit code 0 if all succeeded.

#### Scenario: Instrument has no OHLCV data
- **WHEN** the CLI processes an instrument that has no `1d` candles in the `ohlcv` table
- **THEN** that instrument is skipped, the error is logged to stderr, and processing continues with the next instrument

#### Scenario: All instruments succeed
- **WHEN** the CLI processes a set of instruments and all compute without error
- **THEN** the process exits with code 0

#### Scenario: At least one instrument fails
- **WHEN** the CLI processes a set of instruments and at least one raises an error
- **THEN** the process exits with code 1 after processing all instruments

---

### Requirement: Results written to trading_strategies
The CLI SHALL write each computed indicator value to the `trading_strategies` table using an UPSERT, including the strategy name, indicator name, value, and the parameters used for computation.

#### Scenario: Indicators persisted after computation
- **WHEN** `compute-indicators --strategy best_sma --symbol BTC` completes successfully
- **THEN** rows for `(btc-instrument-id, "best_sma", "sma_low")` and `(btc-instrument-id, "best_sma", "sma_high")` exist in `trading_strategies` with the computed values and `parameters` reflecting the CLI arguments used

#### Scenario: Re-run overwrites existing values
- **WHEN** `compute-indicators` is run a second time for the same symbol and strategy
- **THEN** the existing rows are overwritten (UPSERT) with the new values and an updated `computed_at`

---

### Requirement: Progress output
The CLI SHALL print a summary line per instrument to stdout: ticker, result (`OK` or `ERROR: <message>`), and elapsed time.

#### Scenario: Successful instrument output
- **WHEN** an instrument is computed successfully
- **THEN** a line like `BTC  OK  (2.34s)` is printed to stdout

#### Scenario: Failed instrument output
- **WHEN** an instrument fails
- **THEN** a line like `XYZ  ERROR: No OHLCV data  (0.01s)` is printed to stdout
