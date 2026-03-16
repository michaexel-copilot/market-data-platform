# Trading Strategies Store

## Purpose

Defines the persistent storage schema for precomputed strategy indicator values in DuckDB.

## ADDED Requirements

### Requirement: trading_strategies table schema
The system SHALL store precomputed indicator values in a table named `trading_strategies` with columns: `instrument_id` (VARCHAR, NOT NULL), `strategy_name` (VARCHAR, NOT NULL), `indicator_name` (VARCHAR, NOT NULL), `indicator_value` (DOUBLE, NOT NULL), `parameters` (JSON, nullable), `computed_at` (TIMESTAMPTZ, NOT NULL, default `now()`). The PRIMARY KEY SHALL be `(instrument_id, strategy_name, indicator_name)`.

#### Scenario: Indicator row inserted
- **WHEN** a strategy computation produces an indicator value for a given instrument
- **THEN** a row is inserted into `trading_strategies` with all non-null fields populated and `computed_at` set to the current UTC time

#### Scenario: Existing indicator value overwritten
- **WHEN** a strategy computation runs again for an instrument and indicator that already has a row
- **THEN** the existing row is replaced (UPSERT) and `computed_at` is updated to the new computation time

#### Scenario: Parameters stored as JSON
- **WHEN** a strategy computation is performed with parameters (e.g. `{"sl_short": 10, "sl_long": 10, "pos_usd": 100}`)
- **THEN** the `parameters` column stores those values as a JSON object alongside the indicator value

---

### Requirement: Migration applies idempotently
The `trading_strategies` table SHALL be created by a numbered migration file (`017_trading_strategies.sql`) that is tracked in the `_migrations` table and can be re-run without error.

#### Scenario: Migration applied to fresh database
- **WHEN** `uv run migrate` is executed on a database that does not contain `trading_strategies`
- **THEN** the table is created and the migration is recorded in `_migrations`

#### Scenario: Migration skipped on already-migrated database
- **WHEN** `uv run migrate` is executed on a database that already has `017_trading_strategies.sql` recorded in `_migrations`
- **THEN** the migration file is skipped without error and the table is unchanged
