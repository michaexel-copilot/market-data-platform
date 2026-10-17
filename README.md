# Market Data Platform

A unified, multi-asset-class market data platform backed by PostgreSQL + [TimescaleDB](https://www.timescale.com/). Collects, stores, and serves instrument reference data, fundamental attributes, and OHLCV time-series from 14 data providers through a single REST / gRPC / JSON-RPC API surface.

---

## Features

| Area | Description |
|---|---|
| **Instrument Registry** | Master table for all instruments (crypto, equity, ETF, FX, commodity) with per-asset-class attribute tables and a cross-reference identifier table |
| **OHLCV Time-Series** | 1m / 5m / 1h / 1d native storage; weekly and monthly derived views |
| **Data Source Connectors** | 14 pluggable adapters with rate limiting: CoinGecko, CoinCodex, CoinMarketCap, EODHD, Yahoo Finance, Polygon.io, Alpha Vantage, Tiingo, FMP, Binance, Kraken, OpenFIGI, SEC EDGAR, Nasdaq Data Link |
| **CMC Static Importer** | Batch-import pre-downloaded CoinMarketCap TSV snapshots; idempotent; enriches `instrument_crypto` with CMC ids and ranks |
| **REST API** | FastAPI — instruments list/detail, fundamentals, OHLCV |
| **gRPC API** | `ListInstruments`, `GetInstrument`, `GetOHLCV` (streaming), `GetFundamentals` |
| **JSON-RPC 2.0 API** | Same capabilities as REST at `POST /jsonrpc` |
| **Scheduler Admin** | DB-backed enable/disable of background ingestion jobs; REST API + Management Console UI |
| **Management Console** | Browser UI at `/console` — browse instruments by asset class, view fundamentals, trigger imports; Scheduler pane to enable/disable ingestion jobs |

---

## Requirements

- Python ≥ 3.12
- [uv](https://github.com/astral-sh/uv) package manager

---

## Quick Start

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd market-data-platform
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your API keys and paths
```

Key settings:

```ini
DATABASE_URL=postgresql://market_data:<pw>@localhost/market_data_platform
HTTP_PORT=8010                   # REST API port (default: 8010)
GRPC_PORT=50060                  # gRPC port (default: 50060)
CMC_STATIC_DIR=/path/to/cmc/snapshots   # for the CMC importer
```

### 3. Run database migrations

```bash
uv run migrate
```

This applies all pending SQL migrations to the PostgreSQL database specified by `DATABASE_URL`.

### 4. Start the server

```bash
uv run serve
```

This starts both the REST/JSON-RPC server and the gRPC server in a single process:

| Service | Default address |
|---|---|
| REST + JSON-RPC | `http://localhost:8010` |
| gRPC | `localhost:50060` |
| Interactive API docs | `http://localhost:8010/docs` |
| Management Console | `http://localhost:8010/console` |

To override ports without editing `.env`:

```bash
HTTP_PORT=9000 GRPC_PORT=9001 uv run serve
```

---

## Available Commands

| Command | Description |
|---|---|
| `uv run serve` | Start REST + gRPC servers (runs migrations first) |
| `uv run migrate` | Apply pending database migrations |
| `uv run ingest` | Run all configured connectors once |
| `uv run scheduler` | Start the background ingestion scheduler |
| `uv run market-data import-cmc-static [DIR]` | Import CoinMarketCap TSV snapshots |
| `uv run import-cryptocompare stage` | Load CryptoCompare flat file into staging table (`stg_cryptocompare_1h`) |
| `uv run import-cryptocompare migrate` | Upsert staged 1h rows into the `ohlcv` hypertable |
| `uv run import-cryptocompare aggregate-daily` | Derive and upsert 1d candles from staged 1h data |
| `uv run download-cryptodatadownload-1h --symbol BTC \| --all` | Download hourly OHLCV flat files from cryptodatadownload.com |
| `uv run import-cryptodatadownload-1h --symbol BTC \| --all` | Import downloaded cryptodatadownload.com 1h flat files into the `ohlcv` hypertable |
| `uv run import-hl-pairs` | Fetch and upsert Hyperliquid perpetual pairs |
| `uv run import-source-intersection` | Rebuild `instrument_source_intersection` from live source coverage |
| `uv run compute-indicators` | Bulk-compute trading strategy indicators and store results |

---

## REST API

Base URL: `http://localhost:8010`

### Instruments

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/instruments` | List instruments. Query params: `asset_class`, `is_active` (default `true`), `q` (search), `page`, `page_size` (max 200) |
| `GET` | `/v1/instruments/{symbol}` | Get a single instrument by UUID, `TICKER.MIC`, or ticker |
| `GET` | `/v1/instruments/{symbol}/fundamentals` | Get asset-class-specific fundamental data |

### OHLCV

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/ohlcv/{symbol}` | Time-series candles. Required: `interval` (`1m`,`5m`,`1h`,`1d`,`1w`,`1mo`). Optional: `since`, `until`, `page`, `page_size` (max 5000) |

### Trading Strategies

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/trading-strategies/{symbol}` | Retrieve pre-computed indicator values. Optional query param: `strategy_name` |
| `POST` | `/v1/trading-strategies/{symbol}/compute` | Compute and store indicator values on-demand for one instrument |

**Example:**

```bash
curl "http://localhost:8010/v1/trading-strategies/BTC?strategy_name=best_sma"
```

Returns `404` if no values have been computed yet. Use `compute-indicators` (see below) or the `POST` endpoint to populate.

### Admin

All endpoints are prefixed `/v1/admin`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/admin/import-ohlcv` | Trigger OHLCV import for one instrument + interval |
| `POST` | `/v1/admin/import-ohlcv-cache` | Import OHLCV from local cache folder |
| `POST` | `/v1/admin/migrate-fundamentals` | Promote instruments from staging to master table |
| `POST` | `/v1/admin/import-cmc-static` | Import CoinMarketCap TSV snapshots from server filesystem |
| `POST` | `/v1/admin/import-hl-pairs` | Fetch and upsert Hyperliquid perpetual pairs |
| `POST` | `/v1/admin/run-ingest` | Manually trigger an ingestion job for a specific interval |
| `POST` | `/v1/admin/smart-update-ohlcv` | Automated multi-step OHLCV update: freshness check, 1h ingest, Binance 1m gap fill and 1m→1h aggregation for a single instrument |
| `POST` | `/v1/admin/compute-indicators` | Compute strategy indicators (bulk or per-symbol) |
| `GET` | `/v1/admin/scheduler/jobs` | List scheduler jobs with enabled state |
| `POST` | `/v1/admin/scheduler/jobs/{job_id}/enable` | Enable a scheduler job |
| `POST` | `/v1/admin/scheduler/jobs/{job_id}/disable` | Disable a scheduler job |

### Other

| Method | Path | Description |
|---|---|---|
| `POST` | `/jsonrpc` | JSON-RPC 2.0 endpoint. Methods: `instruments.list`, `instruments.get`, `ohlcv.get`, `instruments.fundamentals` |
| `GET` | `/console` | Management Console SPA |
| `GET` | `/docs` | Interactive Swagger UI |

**Example:**

```bash
curl "http://localhost:8010/v1/instruments?asset_class=crypto&q=BTC"
```

---

## gRPC API

Proto definition: [`proto/v1/market_data.proto`](proto/v1/market_data.proto)

| RPC | Description |
|---|---|
| `ListInstruments` | Paginated instrument list with asset class filter |
| `GetInstrument` | Single instrument by symbol |
| `GetOHLCV` | Server-streaming OHLCV candles |
| `GetFundamentals` | Asset-class-specific fundamental data |

---

## CoinMarketCap Static Importer

Import pre-downloaded TSV snapshots from the CoinMarketCap API:

```bash
uv run market-data import-cmc-static /path/to/snapshots
# or set CMC_STATIC_DIR in .env and run:
uv run market-data import-cmc-static
```

Each snapshot set contains four files with a shared `YYYY-MM-DD_HHMMSS` prefix:

| File pattern | Content |
|---|---|
| `*_listing_data.tsv` | Per-coin price, market cap, supply, rank |
| `*_map_data.tsv` | CMC id ↔ slug canonical mapping |
| `*_categories_data.tsv` | Category master records |
| `*_category_data.tsv` | Per-category coin associations |

The importer is idempotent — re-running on an already-imported directory is safe. It also enriches `instrument_crypto` with `cmc_id`, `cmc_slug`, and `cmc_rank` where a slug match is found. See [docs/import-coinmarketcap-static.md](docs/import-coinmarketcap-static.md) for details.

---

## Management Console

Open `http://localhost:8010/console` in your browser.

### Instruments tab (default)

- **Asset-class selector** — switch between crypto / equity / ETF / FX / commodity
- **Source filter** — narrow instrument list by data source (eodhd, hl, yahoo-finance, cmc)
- **Instrument list** — scrollable left pane with live filter input
- **Fundamentals pane** — key-value display of asset-class-specific attributes, OHLCV time ranges, data-available matrix, and pre-computed BEST SMA Exit V1 indicators
- **Action buttons** — **Update OHLCV Data** (smart multi-step update: 1h freshness check, conditional 1h ingest, Binance 1m gap fill and 1m→1h aggregation), Compute BEST SMA Exit V1, Migrate Fundamental Data

### Scheduler tab

- Lists all four background ingestion jobs (`ohlcv_1m`, `ohlcv_5m`, `ohlcv_1h`, `ohlcv_1d`) with their current enabled state
- **Enable / Disable** buttons take effect immediately (live scheduler pause/resume) and persist to the database

See [docs/management-console.md](docs/management-console.md) for the full UI element reference.

---

## Database Schema

Managed via sequential SQL migrations in `src/market_data/db/migrations_pg/`:

| Migration | Tables / Views / Changes |
|---|---|
| `001` | `instruments` |
| `002` | `instrument_identifiers` |
| `003` | `instrument_crypto` |
| `004` | `instrument_equity` |
| `005` | `instrument_etf` |
| `006` | `instrument_fx` |
| `007` | `instrument_commodity` |
| `008` | `ohlcv` |
| `009` | `ohlcv_weekly`, `ohlcv_monthly` (plain views) |
| `010` | `cmc_import_log`, `cmc_listing_snapshots`, `cmc_coin_tags`, `cmc_categories`, `cmc_category_coins`, `cmc_map` |
| `011` | Adds `cmc_id`, `cmc_slug`, `cmc_rank` to `instrument_crypto` |
| `012` | `data_source` |
| `013` | `attribute_source_map` |
| `014` | `ticker_source_map` |
| `015` | `ohlcv_data_available` |
| `016` | Seeds eodhd data source; populates `ohlcv_data_available` |
| `017` | `trading_strategies` |
| `018` | Enables TimescaleDB extension |
| `019` | Converts `ohlcv` to TimescaleDB hypertable |
| `020` | Converts `cmc_listing_snapshots` to TimescaleDB hypertable |
| `021` | Replaces plain views with TimescaleDB continuous aggregates (`ohlcv_weekly`, `ohlcv_monthly`) |
| `022` | `instrument_hyperliquid` |
| `023` | Seeds Hyperliquid data source |
| `024` | `instrument_source_intersection` |
| `025` | `stg_cryptocompare_1h`; seeds CryptoCompare data source |
| `026` | Adds `tick_1h` column to `ohlcv` |
| `027` | Adds `tick_1d` column to `ohlcv` |
| `028` | `asset_not_found` |
| `029` | `scheduler_jobs` |
| `030` | Adds `is_aggregated BOOLEAN NOT NULL DEFAULT FALSE` column to `ohlcv` (marks synthetic candles aggregated from finer-grained data) |

---

## Compute Indicators CLI

Pre-compute trading strategy indicators and persist them to the `trading_strategies` table so that the REST API and downstream clients can retrieve results instantly without running expensive grid-search computations at request time.

```bash
uv run compute-indicators --strategy best_sma [OPTIONS]
```

**Arguments**

| Argument | Required | Default | Description |
|---|---|---|---|
| `--strategy` | **yes** | — | Strategy name to run (e.g. `best_sma`) |
| `--symbol` | no | *(all instruments)* | Restrict computation to a single instrument ticker (e.g. `BTC`) |
| `--sl-short` | no | `10` | Stop-loss percentage for short positions |
| `--sl-long` | no | `10` | Stop-loss percentage for long positions |
| `--pos-usd` | no | `100` | Simulated position size in USD |

**Examples**

```bash
# Compute best_sma for every instrument in the database
uv run compute-indicators --strategy best_sma

# Compute only for BTC
uv run compute-indicators --strategy best_sma --symbol BTC

# Custom stop-loss and position size
uv run compute-indicators --strategy best_sma --sl-short 5 --sl-long 8 --pos-usd 500
```

The command exits with code `0` on success or `1` if any instrument failed (errors are printed to stderr while successful instruments continue processing). Results are upserted — re-running is safe and idempotent.

## Data Sources

| Provider | Asset Classes | Intervals | Cost |
|---|---|---|---|
| CoinGecko | Crypto | 1d (intraday on paid) | Free tier + paid |
| CoinCodex | Crypto | 1d | Free |
| CoinMarketCap | Crypto | 1d, 1h/5m (paid) | Free tier + paid |
| EODHD | Equities, ETFs, FX, Crypto, Indices | 1m–1d | Paid |
| Yahoo Finance | Equities, ETFs, FX, Crypto | 1m–1d | Free (unofficial) |
| Polygon.io | US Equities, ETFs, FX, Crypto | 1s–1d | Free tier + paid |
| Alpha Vantage | Equities, FX, Crypto, Commodities | 1m–1d | Free (rate limited) |
| Tiingo | US Equities, ETFs, FX, Crypto | 1m, 1h, 1d | Free tier + paid |
| FMP | Equities, ETFs, Crypto, FX | 1m–1d | Free tier + paid |
| Binance | Crypto | 1m–1w | Free |
| Kraken | Crypto | 1m–1d | Free |
| CryptoDataDownload | Crypto | 1h (historical import) | Free |
| OpenFIGI | All (reference only) | — | Free |
| SEC EDGAR | US Equities | Quarterly | Free |
| Nasdaq Data Link | Commodities, Macro | 1d | Free tier + paid |

---

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
uv run python -m pytest

# Lint
uv run ruff check src tests

# Type check
uv run mypy src
```

---

## Project Structure

```
src/market_data/
├── api/
│   ├── rest/          # FastAPI routers (instruments, ohlcv, admin, console)
│   ├── grpc/          # gRPC servicer + generated stubs
│   └── jsonrpc/       # JSON-RPC 2.0 handler
├── cli/               # CLI entry points
├── connectors/        # 14 data source adapters
├── db/
│   ├── migrations_pg/ # SQL DDL files (001–029)
│   ├── connection.py  # PostgreSQL connection manager (psycopg3)
│   ├── migrate.py     # Migration runner
│   ├── scheduler_jobs.py  # load_job_states / set_job_enabled helpers
│   └── resolver.py    # Symbol → instrument_id resolution
├── ingestion/         # Scheduler (APScheduler), job registry, writer
├── models/            # Pydantic models and enums
└── strategies/        # Trading strategy implementations
docs/
├── management-console.md
├── import-coinmarketcap-static.md
└── schema.md
proto/v1/market_data.proto
```
