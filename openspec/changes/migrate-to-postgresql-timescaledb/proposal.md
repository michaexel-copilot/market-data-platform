## Why

DuckDB holds an exclusive file lock that prevents any second process from opening the database while the service is running — even in read-only mode — forcing the workaround of stopping the service or copying the file to inspect data. PostgreSQL uses MVCC, so any number of read clients (DBeaver, psql, TablePlus, analytics scripts) can connect concurrently without affecting the running service. TimescaleDB adds native time-series features (hypertable partitioning, `first()`/`last()` aggregates, `time_bucket()`, compression) that align exactly with the OHLCV access patterns.

## What Changes

- **BREAKING** Replace DuckDB with PostgreSQL 16 + TimescaleDB 2 as the storage backend
- Rewrite `db/connection.py` to use `psycopg[binary]` (psycopg3) instead of `duckdb`
- Adapt all 17 migration SQL files for PostgreSQL syntax (type names, upsert syntax, sequences, `first()`/`last()` aggregate replacement via TimescaleDB)
- Convert the `ohlcv` table to a TimescaleDB hypertable partitioned by `ts` (monthly chunks) with space partitioning by `instrument_id`
- Convert `cmc_listing_snapshots` to a TimescaleDB hypertable partitioned by `snapshot_ts`
- Replace `ohlcv_weekly` and `ohlcv_monthly` views with TimescaleDB continuous aggregates
- Fix all Python query code: `?` → `%s` placeholders, `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`, connection/cursor API
- Add `DATABASE_URL` environment variable replacing `DUCKDB_PATH`
- Provide a one-shot data migration script: DuckDB → export Parquet/CSV → PostgreSQL COPY
- Update all tests to use PostgreSQL (via Docker/pg_ctl) or a `pytest-postgresql` fixture instead of DuckDB in-memory

## Capabilities

### New Capabilities

- `postgresql-backend`: Connection management, migration runner, and schema for PostgreSQL + TimescaleDB. Replaces `duckdb` dependency; introduces `psycopg[binary]` and `timescaledb`. Covers `DATABASE_URL` configuration, connection pooling, hypertable setup for `ohlcv` and `cmc_listing_snapshots`, and continuous aggregates for weekly/monthly rollups.
- `data-migration-tooling`: One-shot CLI tool (`uv run migrate-from-duckdb`) that exports all tables from the existing DuckDB file to CSV/Parquet and bulk-loads them into PostgreSQL via `COPY`. Idempotent (truncate-then-load or skip-if-populated).

### Modified Capabilities

- `time-series-ohlcv`: `ohlcv` becomes a hypertable; `ohlcv_weekly` and `ohlcv_monthly` become continuous aggregates (behavior identical, implementation changes). `DOUBLE` → `DOUBLE PRECISION`, schema-level constraints preserved.
- `strategy-engine`: The `best_sma` SQL CTE uses `%s` placeholders and psycopg3 cursor API instead of DuckDB's `?` / direct connection execute.
- `compute-indicators-rest`: Same REST interface, but internal DB calls go through psycopg3 cursor.
- `ohlcv-cache-importer`: `import_from_cache` upsert uses `ON CONFLICT ... DO UPDATE` (identical to current DuckDB syntax — no change needed in SQL, only parameter placeholder style).

## Impact

- **Dependencies**: Remove `duckdb>=1.5.0`, add `psycopg[binary]>=3.2`, optionally `psycopg-pool>=3.2`
- **Environment**: `DUCKDB_PATH` env var retired; `DATABASE_URL` (e.g. `postgresql://market_data:...@localhost/market_data_platform`) added
- **Tests**: All 4 test files that patch `duckdb.connect(":memory:")` must be updated to use `pytest-postgresql` or a shared test DB
- **Deployment**: PostgreSQL 16 + TimescaleDB 2 must be installed on the host; `sudo -u postgres createdb/createuser` setup needed once
- **Existing data**: DuckDB file at `/appdata/market-data-platform/db/market_data.duckdb` (428 MB) must be migrated before decommissioning DuckDB
- **Service downtime**: One maintenance window needed for the data migration (~30 min estimated for 428 MB)
