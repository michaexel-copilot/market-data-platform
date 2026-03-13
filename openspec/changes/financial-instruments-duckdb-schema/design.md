## Context

This is a greenfield market data platform. There is no existing system to migrate or integrate with. The platform must serve downstream apps that need:

- A reliable, queryable store of instrument reference data across asset classes
- Multi-interval OHLCV time-series data ingested from multiple providers
- A single API surface (REST, gRPC, JSON-RPC) abstracting all provider differences

**Constraints:**

- Single-node deployment; no distributed infra required at this stage
- Python stack managed exclusively with `uv` (no pip, no poetry, no conda)
- DuckDB as the only database engine (no Postgres, no Redis, no message broker)
- Providers have varying rate limits, auth models, and data shapes — must be handled per-connector
- EODHD subscription is the most capable paid source; it sets the expectations for interval coverage

---

## Goals / Non-Goals

**Goals:**
- Define the DuckDB schema for static instrument data (all asset classes) and OHLCV time-series data
- Define a connector interface and per-provider adapters for all 14 listed sources
- Build a unified API exposing instruments, fundamentals, and OHLCV over REST, gRPC, and JSON-RPC
- Support scheduled ingestion at 1d, 1h, 5m, and 1m intervals with deduplication
- Derive weekly and monthly OHLCV as DuckDB views; no separate storage needed

**Non-Goals:**
- Real-time streaming / WebSocket push to clients (read/pull API only at this stage)
- Multi-node or distributed deployment
- User authentication on the API (internal service-to-service; auth is a separate capability)
- Order book, trade tick, or Level 2 data
- Backtesting engine or strategy framework
- Writing data into the platform via API (ingest is internal-only, via connectors)

---

## Decisions

### D1 — DuckDB as primary store (not PostgreSQL)

**Decision:** Use a single DuckDB database file (`market_data.duckdb`) as the sole storage engine for both static and time-series data.

**Rationale:**
- OHLCV data is append-heavy and analytically queried (range scans, aggregations) — DuckDB's columnar format is ideal
- No connection pooling or server process required; the Python service owns the file exclusively
- DuckDB's Parquet export/import provides a natural archival and portability path
- Avoids operational overhead of running and managing PostgreSQL
- DuckDB handles the scale of a single-node market data store comfortably (hundreds of millions of rows)

**Alternative considered:** PostgreSQL with TimescaleDB — more operational overhead, requires a separate process, better for multi-client concurrent writes (not needed here).

---

### D2 — Single DuckDB file, partitioned by asset_class + interval inside the schema

**Decision:** One `market_data.duckdb` file. Time-series stored in a single `ohlcv` table with `(asset_class, interval, instrument_id, ts)` as the primary key / sort order. No per-asset or per-interval files.

**Rationale:**
- Cross-asset queries (e.g. "all 1d data for a list of mixed instruments") are simpler with a single table
- DuckDB's column pruning and zone maps handle large tables efficiently when sorted by the key columns
- Avoids file management complexity of sharded files

**Alternative considered:** Parquet files per `(asset_class, interval, date)` with DuckDB as a query layer — better for archival/cloud offload but adds complexity for writes and point queries.

---

### D3 — Python service layout (uv-managed, single package)

**Decision:** Single Python package `market_data` under `src/market_data/`, managed entirely with `uv`. Entry points exposed via `pyproject.toml` scripts.

**Project layout:**
```
src/
  market_data/
    db/             # DuckDB schema DDL, migrations, connection management
    connectors/     # Per-provider adapters (one module per source)
    ingestion/      # Scheduler + orchestration logic
    api/
      rest/         # FastAPI app
      grpc/         # gRPC servicer + generated protobuf stubs
      jsonrpc/      # JSON-RPC handler (mounted on FastAPI)
    models/         # Pydantic models shared across API layers
    cli/            # uv-runnable CLI for manual ingestion, backfill, admin
pyproject.toml
uv.lock
```

**Key `uv` scripts:**
```toml
[project.scripts]
serve        = "market_data.api:serve"          # starts all API servers
ingest       = "market_data.ingestion:run_once" # manual ingest trigger
scheduler    = "market_data.ingestion:run_scheduler"
migrate      = "market_data.db:migrate"
```

Run with: `uv run serve`, `uv run ingest`, `uv run scheduler`, `uv run migrate`

---

### D4 — Connector interface (protocol-based, not ABC)

**Decision:** Define a `Connector` `Protocol` (structural typing) rather than an abstract base class. Each provider module implements a `fetch_ohlcv()`, `fetch_instruments()`, and optionally `fetch_fundamentals()` function matching the protocol signature.

```python
class Connector(Protocol):
    name: str
    supported_asset_classes: list[AssetClass]
    supported_intervals: list[Interval]

    async def fetch_ohlcv(
        self, instrument_id: str, interval: Interval, since: datetime, until: datetime
    ) -> list[OHLCVRecord]: ...

    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]: ...

    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None: ...
```

**Rationale:**
- Protocol allows duck-typing; connectors don't need to import a base class
- Each connector file is standalone and independently testable
- New connectors can be added without touching a registry — a `connectors/__init__.py` discovers and registers them by scanning the package

**Alternative considered:** ABC with `@abstractmethod` — works but creates a tighter coupling and import dependency on the base module in every connector.

---

### D5 — API framework choices

| Layer | Choice | Rationale |
|---|---|---|
| REST + JSON-RPC | FastAPI | Async, Pydantic integration, excellent OpenAPI generation |
| JSON-RPC | Mounted as a POST endpoint on FastAPI (`/jsonrpc`) | Reuses FastAPI's async stack; no separate server |
| gRPC | `grpcio` + `grpcio-tools`; separate port (50051) | Standard gRPC; proto definitions live in `proto/` |
| ASGI server | `uvicorn` (via `uv run serve`) | Lightweight, asyncio-native |

Both FastAPI (port 8000) and gRPC (port 50051) run in the same process using `asyncio.gather` over separate servers.

---

### D6 — Ingestion scheduler

**Decision:** Use `APScheduler` (async, in-process) for interval-based ingestion jobs. No external broker (no Celery, no Redis).

**Schedule:**
| Interval | Trigger | Sources |
|---|---|---|
| 1m | Every minute | Binance, Polygon.io (crypto + US equities) |
| 5m | Every 5 min | EODHD intraday, CoinMarketCap (paid) |
| 1h | Top of hour | EODHD, CoinGecko (paid), CMC (paid) |
| 1d | 00:05 UTC | All sources (EOD batch) |

Jobs write to DuckDB via `INSERT OR REPLACE` (upsert by primary key). Deduplication is enforced at the DB level via a `UNIQUE` constraint on `(instrument_id, interval, ts)`.

---

### D7 — OHLCV table schema

```sql
CREATE TABLE ohlcv (
    instrument_id   VARCHAR      NOT NULL,
    interval        VARCHAR      NOT NULL,  -- '1m','5m','1h','1d'
    ts              TIMESTAMPTZ  NOT NULL,
    open            DOUBLE       NOT NULL,
    high            DOUBLE       NOT NULL,
    low             DOUBLE       NOT NULL,
    close           DOUBLE       NOT NULL,
    volume          DOUBLE,
    vwap            DOUBLE,
    trade_count     INTEGER,
    market_cap      DOUBLE,                -- for crypto: updated at 1d
    source          VARCHAR      NOT NULL,
    ingested_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, interval, ts)
);
```

Weekly/monthly OHLCV derived as views:
```sql
CREATE VIEW ohlcv_weekly AS
SELECT
    instrument_id,
    '1w' AS interval,
    time_bucket(INTERVAL '7 days', ts) AS ts,
    first(open ORDER BY ts)  AS open,
    max(high)                AS high,
    min(low)                 AS low,
    last(close ORDER BY ts)  AS close,
    sum(volume)              AS volume
FROM ohlcv WHERE interval = '1d'
GROUP BY instrument_id, time_bucket(INTERVAL '7 days', ts);
```

---

### D8 — Symbol resolution strategy

Downstream API callers reference instruments by ticker + exchange (e.g. `AAPL.XNAS`, `BTC-USD`) or by `instrument_id`. The API resolves ambiguous tickers via the `instrument_identifiers` table, always returning the canonical `instrument_id` before querying `ohlcv`.

Resolution priority:
1. Exact `instrument_id` match
2. `ticker_exchange` identifier (`{ticker}.{mic_code}`)
3. Loose `ticker` match within a specified `asset_class`

---

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| DuckDB concurrent write contention — only one writer allowed at a time | Single writer process (scheduler/ingestion); API is read-only against DuckDB. Use WAL mode. |
| Provider rate limits causing ingestion gaps | Per-connector rate limiter (`asyncio` token bucket); exponential backoff; gap-fill job on next run |
| `yfinance` is unofficial and can break without notice | Used only as fallback/backfill; not on critical path. Swap to Tiingo or Alpha Vantage if it breaks. |
| 1m OHLCV data grows very large over time (100 instruments × 525,600 rows/year) | Partition older 1m/5m data to Parquet archives after 90 days; DuckDB queries Parquet natively |
| gRPC proto changes break clients | Version proto files; never remove fields; use field numbers correctly |
| Identifier collisions (same ticker on multiple exchanges) | `instrument_id` is always the canonical key; ticker lookups require `mic_code` or `asset_class` qualifier |

---

## Migration Plan

This is a greenfield system. Setup sequence:

1. `uv init` — initialise the project and `pyproject.toml`
2. `uv add duckdb fastapi uvicorn grpcio grpcio-tools apscheduler pydantic` — add core dependencies
3. `uv run migrate` — run DDL to create all tables and views in `market_data.duckdb`
4. `uv run ingest --source coingecko --asset-class crypto --backfill 90d` — initial backfill
5. `uv run serve` — start API servers on ports 8000 (HTTP) and 50051 (gRPC)
6. `uv run scheduler` — start continuous ingestion (runs alongside `serve` in prod via `uv run serve` which spawns both)

Rollback: delete `market_data.duckdb` and re-run from step 3. No shared state, no external DB to roll back.

---

## Open Questions

1. **Backfill depth for intraday intervals** — how far back should 1m and 5m data be populated at launch? More than 90 days of 1m data per instrument is feasible but large. Recommend: 7 days 1m, 30 days 5m, 1 year 1h, full history 1d.
2. **Multi-process API serving** — should `uvicorn` run with multiple workers? DuckDB's single-writer model means write jobs cannot run concurrently with workers sharing a file handle. Decision needed before production: either single-process with async concurrency, or a read-replica WAL-based approach.
3. **gRPC vs JSON-RPC client priority** — which interface will downstream apps use most? Influences which to invest in first for client library generation.
4. **Instrument universe scope at launch** — start with top-N crypto + major US equities only, or full EODHD universe from day one?
