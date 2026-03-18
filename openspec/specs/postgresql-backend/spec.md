# PostgreSQL Backend

## Purpose

Defines the PostgreSQL connection management, schema migration runner, TimescaleDB hypertable and compression configuration, continuous aggregates for derived OHLCV views, and SQL conventions (parameter placeholders, upsert syntax) for the platform's database backend.

## Requirements

### Requirement: PostgreSQL connection management
The system SHALL manage a persistent PostgreSQL connection via `psycopg[binary]` (psycopg3). The connection SHALL be configured via a `DATABASE_URL` environment variable with the format `postgresql://<user>:<password>@<host>/<dbname>`. The `DUCKDB_PATH` variable is retired.

The connection module SHALL expose `get_connection()` returning a `psycopg.Connection` with `autocommit=True`, and `close_connection()`. Thread-safety SHALL be preserved with a module-level lock.

#### Scenario: Connection created on first call
- **WHEN** `get_connection()` is called for the first time
- **THEN** a psycopg3 connection is opened using `DATABASE_URL` and cached for subsequent calls

#### Scenario: Missing DATABASE_URL
- **WHEN** `DATABASE_URL` is not set and no default is resolvable
- **THEN** the service fails to start with a clear error message indicating the missing variable

#### Scenario: TimescaleDB not available
- **WHEN** the connection is established but TimescaleDB extension is not installed in the target database
- **THEN** the migration runner raises a clear error before creating any tables

---

### Requirement: PostgreSQL migration runner
The system SHALL apply schema migrations from `src/market_data/db/migrations_pg/` in filename-order. Each file SHALL be applied exactly once (idempotency via `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, and `ON CONFLICT DO NOTHING` for seed data).

The migration runner SHALL enable the `timescaledb` extension before running any user migrations.

#### Scenario: Fresh database migration
- **WHEN** `uv run migrate` is invoked against an empty PostgreSQL database
- **THEN** all migration files are applied in order, the `timescaledb` extension is enabled, all tables exist, `ohlcv` is a hypertable, and the command exits with code 0

#### Scenario: Re-run on already-migrated database
- **WHEN** `uv run migrate` is invoked on a database that already has all migrations applied
- **THEN** no changes are made and the command exits with code 0 (fully idempotent)

---

### Requirement: `ohlcv` hypertable with compression
The `ohlcv` table SHALL be converted to a TimescaleDB hypertable partitioned by `ts` with monthly chunks. A hash space partition on `instrument_id` with 4 buckets SHALL be added. Compression SHALL be enabled with `timescaledb.compress_segmentby = 'instrument_id, interval'` and a policy compressing chunks older than 7 days.

#### Scenario: Hypertable created
- **WHEN** the migration for `ohlcv` hypertable is applied to an empty `ohlcv` table
- **THEN** `SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = 'ohlcv'` returns one row

#### Scenario: Bulk insert into hypertable
- **WHEN** `INSERT INTO ohlcv ... ON CONFLICT (instrument_id, interval, ts) DO UPDATE SET ...` is executed with 1000 rows
- **THEN** all rows are stored and retrievable, partitioned into the appropriate monthly chunk

---

### Requirement: Continuous aggregates for weekly and monthly OHLCV
The `ohlcv_weekly` and `ohlcv_monthly` plain views SHALL be replaced by TimescaleDB continuous aggregates. Each continuous aggregate SHALL use `first(open, ts)`, `last(close, ts)`, `max(high)`, `min(low)`, `sum(volume)` grouped by `time_bucket`. A refresh policy SHALL update the aggregates automatically.

#### Scenario: Weekly rollup query
- **WHEN** `SELECT * FROM ohlcv_weekly WHERE instrument_id = 'x' ORDER BY ts DESC LIMIT 52` is executed
- **THEN** the query returns pre-materialised weekly bars with correct open/high/low/close/volume without scanning the full hypertable

#### Scenario: Monthly rollup query
- **WHEN** `SELECT * FROM ohlcv_monthly WHERE instrument_id = 'x' ORDER BY ts DESC LIMIT 12` is executed
- **THEN** the query returns pre-materialised monthly bars

---

### Requirement: Parameter placeholder style
All SQL executed against PostgreSQL SHALL use `%s` positional placeholders (DB-API 2.0 / psycopg3 style). DuckDB `?` placeholders SHALL NOT appear in any SQL string passed to psycopg3.

#### Scenario: Parameterised query executes correctly
- **WHEN** `conn.execute("SELECT * FROM instruments WHERE ticker = %s", ("BTC",))` is called
- **THEN** the query returns the expected row without SQL injection or syntax errors

---

### Requirement: Upsert syntax
All `INSERT OR IGNORE INTO` statements SHALL be replaced with `INSERT INTO ... ON CONFLICT DO NOTHING`. All `INSERT OR REPLACE INTO` statements SHALL be replaced with `INSERT INTO ... ON CONFLICT (...) DO UPDATE SET ...` (preserving existing conflict targets).

#### Scenario: Duplicate insert ignored
- **WHEN** an `INSERT INTO ... ON CONFLICT DO NOTHING` is executed for a row that already exists
- **THEN** no error is raised and the existing row is unchanged
