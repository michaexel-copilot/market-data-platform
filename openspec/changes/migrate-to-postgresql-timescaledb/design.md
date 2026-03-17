## Context

The market-data-platform uses DuckDB as its sole storage backend via a single shared write connection (`db/connection.py`). DuckDB's file-locking model prevents any second process — including read-only clients — from opening the database while the service is running. The current workaround (`view-db.sh`: copy + open copy) is fragile and always stale. The platform is on DuckDB 1.5.0 with PostgreSQL 16.13 already installed locally.

Schema: 17 migration files, ~20 tables. Time-series data lives in `ohlcv` (~50M rows, 428 MB on disk) and `cmc_listing_snapshots`. All SQL is written in DuckDB-flavoured SQL which is largely PostgreSQL-compatible with a handful of differences.

## Goals / Non-Goals

**Goals:**
- Replace DuckDB with PostgreSQL 16 + TimescaleDB 2 as the storage backend
- Enable concurrent read access (DBeaver, psql, analytics scripts) without service downtime
- Preserve all existing REST API and CLI behaviour (no breaking API changes)
- Migrate all existing data from the DuckDB file with no data loss
- Establish a clean `DATABASE_URL`-based connection configuration

**Non-Goals:**
- Setting up PostgreSQL replication (separate future change)
- Connection pooling via PgBouncer (can be added later; psycopg-pool is sufficient for now)
- Changing the REST API schema or any business logic
- Migrating `FindShortOpportunites/web.py` (it reads from market-data-platform via HTTP only)

## Decisions

### D1 — psycopg3 (`psycopg[binary]`) over asyncpg or SQLAlchemy

The entire codebase uses synchronous `conn.execute(sql, params)` patterns — there is no async I/O in the DB layer. psycopg3 exposes `conn.execute()` that returns a cursor directly, making it the closest drop-in to the current DuckDB API. asyncpg would require wrapping every call in `asyncio.run()` or restructuring the whole call chain. SQLAlchemy adds unnecessary abstraction over a codebase that already uses raw SQL.

Alternatives: asyncpg (rejected — sync→async conversion scope), SQLAlchemy (rejected — over-engineering for raw SQL codebase).

### D2 — TimescaleDB hypertable for `ohlcv` with monthly chunks + hash space partition

`ohlcv` is the dominant table (50M rows). Time-range queries dominate access patterns. Monthly chunks allow partition pruning on typical queries (last 30 days, last 6 months) while keeping chunk count manageable (~70 chunks over 5.5 years). Hash space partitioning by `instrument_id` into 4 buckets distributes writes across partitions for bulk imports.

`cmc_listing_snapshots` also gets a hypertable on `snapshot_ts` (weekly chunks, no space partition — fewer rows, fewer instruments).

### D3 — TimescaleDB continuous aggregates replace `ohlcv_weekly` / `ohlcv_monthly` views

The current DuckDB views use `first()` / `last()` aggregate functions (DuckDB-specific). TimescaleDB provides identical `first(value, time)` / `last(value, time)` functions. Continuous aggregates materialise results and refresh automatically, making rollup queries instant instead of scanning the full hypertable on every request.

Alternatives: plain PostgreSQL views with `(array_agg(open ORDER BY ts))[1]` — works but slow on 50M rows; rejected in favour of continuous aggregates.

### D4 — Compressed hypertable for `ohlcv` data older than 7 days

TimescaleDB compression on `(instrument_id, interval)` segmentation typically achieves 10-20× compression on OHLCV data (highly repetitive float columns). We set a 7-day compression policy: data older than 7 days is compressed, recent data stays uncompressed for fast ingest.

### D5 — Parameter placeholder: `?` → `%s` across all Python files

psycopg3 uses `%s` (DB-API 2.0) positional parameters. This is a global search-and-replace across all `.execute()` calls in ingestion, strategy, and API files. The change is mechanical but touches ~18 files. `executemany()` calls use the same `%s` style and remain compatible.

### D6 — Migration SQL files rewritten as PostgreSQL-native (new `src/market_data/db/migrations_pg/`)

Rather than patching the 17 existing DuckDB migration files (which would break the existing test suite that still runs against DuckDB in-memory), the PostgreSQL migrations live in a new `migrations_pg/` directory. The DuckDB migrations remain until the transition is complete and tests are updated. After full cutover the DuckDB migrations can be archived.

### D7 — Data migration: DuckDB export via Parquet → PostgreSQL `COPY`

DuckDB can export tables to Parquet natively (`COPY ... TO ... (FORMAT PARQUET)`). Python then reads each Parquet file with `pyarrow` and bulk-loads via psycopg3's `COPY FROM` binary stream. This avoids CSV quoting issues with JSON/text columns and is the fastest path for 50M rows. Estimated time: 5-15 minutes for the full dataset.

## Risks / Trade-offs

- **Test suite migration** → Run DuckDB-based tests until PostgreSQL-based tests are passing; migrate files one by one
- **`pytest-postgresql` vs shared test DB** → Use `pytest-postgresql` (starts a temporary PostgreSQL cluster per test session) to keep tests hermetic; adds ~5 seconds to test startup
- **TimescaleDB not installed** → Add installation to the setup docs; verify extension is present on startup and emit a clear error if not
- **Continuous aggregates with compressed chunks** → TimescaleDB requires care when backfilling into compressed chunks; `ohlcv` import uses `decompress_chunk()` before bulk writes if needed (or realtime aggregates as fallback)
- **`DOUBLE` vs `DOUBLE PRECISION`** → Minor; handled in migration files

## Migration Plan

```
1. Install TimescaleDB:
   sudo apt install timescaledb-2-postgresql-16
   sudo timescaledb-tune --quiet --yes
   sudo systemctl restart postgresql

2. Create DB and user:
   sudo -u postgres createuser market_data --pwprompt
   sudo -u postgres createdb market_data_platform --owner market_data

3. Run PostgreSQL migrations:
   uv run migrate   (reads DATABASE_URL, applies migrations_pg/)

4. Run data migration (service STOPPED):
   uv run migrate-from-duckdb --source /appdata/market-data-platform/db/market_data.duckdb

5. Verify row counts match DuckDB source.

6. Update .env: DATABASE_URL=postgresql://market_data:...@localhost/market_data_platform

7. Start service, run smoke tests.

Rollback: Keep DuckDB file. If PostgreSQL fails, revert DATABASE_URL to DUCKDB_PATH.
```

## Open Questions

- **psycopg-pool**: Should the service use a connection pool (`psycopg_pool.ConnectionPool`) from the start, or a single persistent connection (matching current DuckDB behaviour)? A pool is safer for concurrent FastAPI requests but adds ~50 lines. Recommend starting with single connection + `autocommit=True` (matches current semantics), pool can be added later.
- **TimescaleDB licensing**: TimescaleDB uses the Timescale License (TSL) for some features. The core hypertable, compression, and continuous aggregates used here are all Apache 2.0 licensed. Confirm acceptable.
