## 1. Project Scaffolding

- [x] 1.1 Run `uv init` and configure `pyproject.toml` with project metadata, Python version constraint (>=3.12), and `[project.scripts]` entries for `serve`, `ingest`, `scheduler`, `migrate`
- [x] 1.2 Create `src/market_data/` package structure: `db/`, `connectors/`, `ingestion/`, `api/rest/`, `api/grpc/`, `api/jsonrpc/`, `models/`, `cli/`
- [x] 1.3 Add core dependencies via `uv add`: `duckdb`, `fastapi`, `uvicorn[standard]`, `grpcio`, `grpcio-tools`, `apscheduler`, `pydantic`, `httpx`, `python-dotenv`
- [x] 1.4 Add provider-specific dependencies via `uv add`: `yfinance`, `nasdaq-data-link`
- [x] 1.5 Add dev dependencies via `uv add --dev`: `pytest`, `pytest-asyncio`, `ruff`, `mypy`
- [x] 1.6 Create `.env.example` with all required API key variables: `COINGECKO_API_KEY`, `CMC_API_KEY`, `EODHD_API_KEY`, `POLYGON_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `TIINGO_API_KEY`, `FMP_API_KEY`, `NASDAQ_DATA_LINK_API_KEY`
- [x] 1.7 Create `proto/v1/market_data.proto` defining `MarketDataService` with `ListInstruments`, `GetInstrument`, `GetOHLCV` (server-streaming), `GetFundamentals` RPCs and all message types
- [x] 1.8 Generate gRPC Python stubs from proto using `uv run python -m grpc_tools.protoc` and place in `src/market_data/api/grpc/generated/`

## 2. DuckDB Schema and Migrations

- [x] 2.1 Implement `src/market_data/db/connection.py` — DuckDB connection manager with WAL mode enabled and a single shared connection instance
- [x] 2.2 Implement `src/market_data/db/migrate.py` — migration runner that executes DDL files in order from `src/market_data/db/migrations/`
- [x] 2.3 Create migration `001_instruments.sql` — `instruments` table DDL with all fields from the Static Fields Model
- [x] 2.4 Create migration `002_instrument_identifiers.sql` — `instrument_identifiers` table DDL with `(instrument_id, id_type, id_value)` unique constraint
- [x] 2.5 Create migration `003_instrument_crypto.sql` — `instrument_crypto` table DDL
- [x] 2.6 Create migration `004_instrument_equity.sql` — `instrument_equity` table DDL
- [x] 2.7 Create migration `005_instrument_etf.sql` — `instrument_etf` table DDL
- [x] 2.8 Create migration `006_instrument_fx.sql` — `instrument_fx` table DDL
- [x] 2.9 Create migration `007_instrument_commodity.sql` — `instrument_commodity` table DDL
- [x] 2.10 Create migration `008_ohlcv.sql` — `ohlcv` table DDL with PRIMARY KEY `(instrument_id, interval, ts)` and `CHECK (interval IN ('1m','5m','1h','1d'))`
- [x] 2.11 Create migration `009_ohlcv_views.sql` — `ohlcv_weekly` and `ohlcv_monthly` view DDL using DuckDB window/aggregation functions
- [x] 2.12 Wire `uv run migrate` entry point to execute all pending migrations

## 3. Pydantic Models

- [x] 3.1 Implement `src/market_data/models/enums.py` — `AssetClass`, `Interval`, `IdType` enums
- [x] 3.2 Implement `src/market_data/models/instrument.py` — `InstrumentRecord`, `InstrumentCryptoRecord`, `InstrumentEquityRecord`, `InstrumentETFRecord`, `InstrumentFXRecord`, `InstrumentCommodityRecord`, `IdentifierRecord`
- [x] 3.3 Implement `src/market_data/models/ohlcv.py` — `OHLCVRecord` with all fields; validate `interval` against allowed values
- [x] 3.4 Implement `src/market_data/models/fundamentals.py` — `FundamentalsRecord` as union of asset-class-specific models
- [x] 3.5 Implement `src/market_data/models/api.py` — request/response models: `PaginatedResponse[T]`, `OHLCVRequest`, `InstrumentListRequest`, `ErrorResponse`

## 4. Connector Interface and Registry

- [x] 4.1 Implement `src/market_data/connectors/protocol.py` — `Connector` Protocol definition with `fetch_ohlcv`, `fetch_instruments`, `fetch_fundamentals` signatures
- [x] 4.2 Implement `src/market_data/connectors/rate_limiter.py` — asyncio token-bucket rate limiter with configurable rate and burst
- [x] 4.3 Implement `src/market_data/connectors/base.py` — shared utilities: UTC timestamp normalisation, string-to-float price casting, exponential backoff decorator
- [x] 4.4 Implement `src/market_data/connectors/__init__.py` — auto-discovery registry that scans the package for module-level `connector` objects and indexes by name, asset class, and interval

## 5. Provider Connector Implementations

- [x] 5.1 Implement `connectors/coingecko.py` — `fetch_instruments` (coins list) and `fetch_ohlcv` (OHLC endpoint, 1d); `fetch_fundamentals` (coin detail endpoint)
- [x] 5.2 Implement `connectors/coincodex.py` — `fetch_instruments` and `fetch_ohlcv` (1d); `fetch_fundamentals`
- [x] 5.3 Implement `connectors/coinmarketcap.py` — `fetch_instruments`, `fetch_ohlcv` (1d, 1h on paid, 5m on paid), `fetch_fundamentals`
- [x] 5.4 Implement `connectors/eodhd.py` — `fetch_instruments` (bulk tickers), `fetch_ohlcv` (1m, 5m, 1h, 1d), `fetch_fundamentals` (fundamentals endpoint)
- [x] 5.5 Implement `connectors/yahoo_finance.py` — `fetch_ohlcv` using `yfinance` (1m 7d, 5m, 1h, 1d); mark as fallback-only
- [x] 5.6 Implement `connectors/polygon.py` — `fetch_ohlcv` (1m, 5m, 1h, 1d for US equities and crypto); WebSocket ingest hook for 1m real-time
- [x] 5.7 Implement `connectors/alpha_vantage.py` — `fetch_ohlcv` (1m, 5m, 15m, 30m, 1h, 1d) for equities, FX, crypto
- [x] 5.8 Implement `connectors/tiingo.py` — `fetch_ohlcv` (1m, 1h, 1d via IEX feed)
- [x] 5.9 Implement `connectors/fmp.py` — `fetch_ohlcv` (1m, 5m, 1h, 1d); `fetch_fundamentals` (income statement, balance sheet fields mapped to `InstrumentEquityRecord`)
- [x] 5.10 Implement `connectors/binance.py` — `fetch_ohlcv` (1m, 5m, 1h, 1d, 1w) using public REST API klines endpoint; no API key required
- [x] 5.11 Implement `connectors/kraken.py` — `fetch_ohlcv` (1m, 5m, 1h, 1d) for crypto pairs
- [x] 5.12 Implement `connectors/openfigi.py` — `fetch_instruments` only: batch map tickers to FIGI/ISIN/CUSIP identifiers; `fetch_ohlcv` raises `NotImplementedError`
- [x] 5.13 Implement `connectors/sec_edgar.py` — `fetch_fundamentals` only: fetch company facts JSON from EDGAR API; `fetch_ohlcv` raises `NotImplementedError`
- [x] 5.14 Implement `connectors/nasdaq_data_link.py` — `fetch_ohlcv` (1d) and `fetch_fundamentals` for commodities and macro series

## 6. Symbol Resolution

- [x] 6.1 Implement `src/market_data/db/resolver.py` — `resolve_symbol(symbol, asset_class=None) -> str` function implementing the three-step resolution priority (UUID → ticker_exchange → loose ticker)
- [x] 6.2 Add `ambiguous symbol` error type and `unknown symbol` error type to `models/api.py`
- [x] 6.3 Write unit tests for resolver covering: exact UUID match, `TICKER.MIC` match, ambiguous bare ticker, unknown symbol

## 7. Ingestion Engine and Scheduler

- [x] 7.1 Implement `src/market_data/ingestion/writer.py` — `write_ohlcv(records: list[OHLCVRecord])` using `INSERT OR REPLACE` into DuckDB `ohlcv` table; `write_instruments(records)` for instrument upserts
- [x] 7.2 Implement `src/market_data/ingestion/jobs.py` — one async job function per interval (`run_1m_job`, `run_5m_job`, `run_1h_job`, `run_1d_job`); each queries the registry for matching connectors and calls `fetch_ohlcv`
- [x] 7.3 Implement `src/market_data/ingestion/scheduler.py` — APScheduler setup with cron/interval triggers: 1m every minute, 5m every 5 min, 1h top of hour, 1d at 00:05 UTC
- [x] 7.4 Implement `src/market_data/ingestion/backfill.py` — `backfill(source, asset_class, interval, since, until)` CLI-callable function for historical data population
- [x] 7.5 Implement `src/market_data/ingestion/archiver.py` — exports `1m`/`5m` rows older than 90 days to Parquet under `archive/` directory and deletes from live table
- [x] 7.6 Wire `uv run ingest` and `uv run scheduler` entry points

## 8. REST and JSON-RPC API

- [x] 8.1 Implement `src/market_data/api/rest/instruments.py` — FastAPI router for `GET /v1/instruments`, `GET /v1/instruments/{symbol}`, `GET /v1/instruments/{symbol}/fundamentals`
- [x] 8.2 Implement `src/market_data/api/rest/ohlcv.py` — FastAPI router for `GET /v1/ohlcv/{symbol}` with `interval`, `since`, `until`, `page`, `page_size` query params; paginated response
- [x] 8.3 Implement `src/market_data/api/rest/errors.py` — exception handlers for `SymbolNotFound` (404), `AmbiguousSymbol` (400), `ValidationError` (422), generic `Exception` (500 without leak)
- [x] 8.4 Implement `src/market_data/api/jsonrpc/handler.py` — JSON-RPC 2.0 dispatcher mounted at `POST /jsonrpc`; methods: `instruments.list`, `instruments.get`, `instruments.fundamentals`, `ohlcv.get`; support batch requests
- [x] 8.5 Implement `src/market_data/api/rest/app.py` — FastAPI app factory: mounts REST routers, JSON-RPC handler, and OpenAPI docs
- [x] 8.6 Verify `GET /openapi.json` and Swagger UI at `GET /docs` are generated correctly

## 9. gRPC API

- [x] 9.1 Implement `src/market_data/api/grpc/servicer.py` — `MarketDataServicer` implementing `ListInstruments`, `GetInstrument`, `GetOHLCV` (server-streaming), `GetFundamentals`; map DuckDB results to proto messages
- [x] 9.2 Implement `src/market_data/api/grpc/server.py` — async gRPC server on port 50051 using `grpcio`
- [x] 9.3 Ensure gRPC server returns `NOT_FOUND` status for unknown symbols and `INVALID_ARGUMENT` for bad params

## 10. Service Entry Point

- [x] 10.1 Implement `src/market_data/api/__init__.py` `serve()` function — starts uvicorn (port 8000) and gRPC server (port 50051) concurrently via `asyncio.gather`
- [x] 10.2 Verify `uv run serve` starts both servers and both are reachable without manual venv activation
- [x] 10.3 Implement graceful shutdown on `SIGTERM`/`SIGINT` — stop scheduler, flush in-progress writes, close DuckDB connection

## 11. Tests

- [x] 11.1 Write unit tests for each connector's field mapping and timestamp normalisation using mocked HTTP responses (no live API calls)
- [x] 11.2 Write integration tests for DuckDB migrations — run all migrations on an in-memory DuckDB instance and assert all tables/views exist
- [x] 11.3 Write tests for symbol resolver covering all three resolution paths and error cases
- [x] 11.4 Write FastAPI integration tests for REST endpoints using `httpx.AsyncClient` and an in-memory DuckDB fixture
- [x] 11.5 Write tests for JSON-RPC handler: valid call, batch call, unknown method (`-32601`), invalid params (`-32602`)
- [x] 11.6 Verify all tests pass with `uv run pytest`
