# Data Migration Tooling

## Purpose

Provides CLI tooling to migrate data from an existing DuckDB database file into the PostgreSQL backend.

## Requirements

### Requirement: migrate-from-duckdb CLI
The system SHALL provide a `migrate-from-duckdb` CLI command (registered as `uv run migrate-from-duckdb`) that exports all data from an existing DuckDB database file and bulk-loads it into the PostgreSQL database.

The CLI SHALL accept:
- `--source` (required): Path to the DuckDB `.duckdb` file
- `--url` (optional): PostgreSQL `DATABASE_URL` override (defaults to env var)
- `--dry-run` (optional): Show row counts per table that would be migrated without writing to PostgreSQL

The migration SHALL proceed table-by-table in a safe order (respecting foreign keys). For each table it SHALL:
1. Export from DuckDB to Parquet in a temp directory
2. Truncate the target PostgreSQL table if `--force` flag is set, otherwise skip tables that already have rows
3. `COPY` from Parquet into PostgreSQL via psycopg3 binary-format stream
4. Log `<TABLE>  OK  (<N> rows, <elapsed>s)` per table

#### Scenario: Full migration succeeds
- **WHEN** `uv run migrate-from-duckdb --source /appdata/.../market_data.duckdb` is invoked against an empty PostgreSQL database
- **THEN** all tables are populated, row counts in PostgreSQL match row counts in DuckDB, and the process exits with code 0

#### Scenario: Dry run shows counts
- **WHEN** `uv run migrate-from-duckdb --source ... --dry-run` is invoked
- **THEN** each table name and its DuckDB row count is printed without writing to PostgreSQL

#### Scenario: Skip already-populated tables
- **WHEN** `migrate-from-duckdb` is invoked and the `instruments` table already has rows in PostgreSQL
- **THEN** that table is skipped with a `SKIP (already has data)` log line unless `--force` is passed

#### Scenario: Source file does not exist
- **WHEN** `--source` points to a non-existent file
- **THEN** the CLI exits with code 1 and an error message before connecting to PostgreSQL
