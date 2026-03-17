## 1. Environment & Infrastructure

- [x] 1.1 Install TimescaleDB: `sudo apt install timescaledb-2-postgresql-16 && sudo timescaledb-tune --quiet --yes && sudo systemctl restart postgresql`
- [x] 1.2 Create PostgreSQL role and database: `sudo -u postgres createuser market_data --pwprompt && sudo -u postgres createdb market_data_platform --owner market_data`
- [x] 1.3 Add `DATABASE_URL` to `.env` (e.g. `postgresql://market_data:<pw>@localhost/market_data_platform`)
- [x] 1.4 Add `psycopg[binary]>=3.2` and `pyarrow>=15.0` to `pyproject.toml`; remove `duckdb` dependency
- [x] 1.5 Add `pytest-postgresql>=6.0` to dev dependencies in `pyproject.toml`

## 2. Connection Layer

- [x] 2.1 Rewrite `src/market_data/db/connection.py` to use psycopg3: read `DATABASE_URL`, open `psycopg.Connection` with `autocommit=True`, expose `get_connection()` and `close_connection()`
- [x] 2.2 Update `src/market_data/api/__init__.py` shutdown hook to call `close_connection()` for psycopg3

## 3. PostgreSQL Migrations (`migrations_pg/`)

- [x] 3.1 Create `src/market_data/db/migrations_pg/` directory and adapt migrations 001–011: replace `DOUBLE` → `DOUBLE PRECISION`, `VARCHAR` → `TEXT`, `JSON` → `JSONB`, `BOOLEAN` unchanged
- [x] 3.2 Adapt migration 012 (`data_source`): replace `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`
- [x] 3.3 Adapt migrations 013–017: same type replacements + `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`
- [x] 3.4 Create `migrations_pg/018_timescaledb_setup.sql`: `CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;`
- [x] 3.5 Create `migrations_pg/019_ohlcv_hypertable.sql`: `SELECT create_hypertable('ohlcv', by_range('ts', INTERVAL '1 month')); SELECT add_dimension(...); ALTER TABLE ohlcv SET (timescaledb.compress, ...); SELECT add_compression_policy('ohlcv', INTERVAL '7 days');`
- [x] 3.6 Create `migrations_pg/020_cmc_listing_snapshots_hypertable.sql`: convert `cmc_listing_snapshots` to a hypertable on `snapshot_ts` with weekly chunks
- [x] 3.7 Create `migrations_pg/021_ohlcv_continuous_aggregates.sql`: replace `ohlcv_weekly` and `ohlcv_monthly` plain views with TimescaleDB continuous aggregates using `first(open, ts)`, `last(close, ts)`, `max(high)`, `min(low)`, `sum(volume)`, `time_bucket()`; add refresh policies
- [x] 3.8 Update `src/market_data/db/migrate.py` to read from `migrations_pg/` and use psycopg3 cursor

## 4. Python SQL — Parameter Placeholders & Upserts

- [x] 4.1 `src/market_data/ingestion/writer.py`: replace `?` → `%s`, update `executemany` cursor usage
- [x] 4.2 `src/market_data/ingestion/import_ohlcv_cache.py`: replace `?` → `%s`, `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`
- [x] 4.3 `src/market_data/ingestion/migrate_fundamentals.py`: replace `?` → `%s`, all three `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`
- [x] 4.4 `src/market_data/ingestion/import_coinmarketcap_static.py`: replace `?` → `%s`, `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`
- [x] 4.5 `src/market_data/ingestion/backfill.py`: replace `?` → `%s`
- [x] 4.6 `src/market_data/api/rest/admin.py`: replace `?` → `%s`, update cursor usage
- [x] 4.7 `src/market_data/api/rest/instruments.py`: replace `?` → `%s`
- [x] 4.8 `src/market_data/api/rest/ohlcv.py`: replace `?` → `%s`
- [x] 4.9 `src/market_data/api/rest/trading_strategies.py`: replace `?` → `%s`
- [x] 4.10 `src/market_data/api/grpc/servicer.py`: replace `?` → `%s`
- [x] 4.11 `src/market_data/api/jsonrpc/handler.py`: replace `?` → `%s`
- [x] 4.12 `src/market_data/db/resolver.py`: replace `?` → `%s`
- [x] 4.13 `src/market_data/strategies/best_sma.py`: replace `?` → `%s`, update cursor usage

## 5. Data Migration CLI

- [x] 5.1 Create `src/market_data/cli/migrate_from_duckdb.py`: accepts `--source`, `--url`, `--dry-run`, `--force`; exports each table from DuckDB to Parquet via `duckdb`; bulk-loads into PostgreSQL via psycopg3 `COPY FROM`; skips tables with existing data unless `--force`
- [x] 5.2 Register `migrate-from-duckdb = "market_data.cli.migrate_from_duckdb:main"` in `pyproject.toml`

## 6. Tests

- [x] 6.1 Update `tests/conftest.py`: replace `duckdb.connect(":memory:")` fixture with `pytest-postgresql` managed PostgreSQL instance; apply `migrations_pg/` against it; expose `db_conn` fixture
- [x] 6.2 Update `tests/test_strategies.py`: replace `duckdb.connect(":memory:")` in `db_with_ohlcv` fixture with psycopg3 cursor against the shared test PostgreSQL; insert `1h` test rows
- [x] 6.3 Update `tests/test_api_rest.py`: replace `patched_db` fixture (all `duckdb.connect(":memory:")`) with psycopg3 fixture; update all inline `patched_db.execute(...)` calls to use cursor
- [x] 6.4 Update `tests/test_migrations.py`: update connection fixture to psycopg3; add assertion `SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = 'ohlcv'` returns one row
- [x] 6.5 Update `tests/test_resolver.py`: update fixture to psycopg3
- [x] 6.6 Run full test suite: `uv run python -m pytest tests/ -v` — all tests pass

## 7. Data Migration (Production)

- [x] 7.1 Stop service: `sudo systemctl stop market-data-platform` (or kill `uv run serve`)
- [x] 7.2 Run PostgreSQL migrations: `uv run migrate`
- [x] 7.3 Run data migration: `uv run migrate-from-duckdb --source /appdata/market-data-platform/db/market_data.duckdb`
- [x] 7.4 Verify row counts: spot-check `ohlcv`, `instruments`, `cmc_listing_snapshots` in psql vs original DuckDB
- [x] 7.5 Start service: `uv run serve`
- [x] 7.6 Run smoke test: `curl http://localhost:8010/v1/instruments` returns data
- [x] 7.7 Archive DuckDB file to `/appdata/market-data-platform/db/archive/` (do not delete yet)
