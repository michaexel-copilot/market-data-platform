# Market Data Platform

A unified, multi-asset-class market data platform backed by [DuckDB](https://duckdb.org/). Collects, stores, and serves instrument reference data, fundamental attributes, and OHLCV time-series from 14 data providers through a single REST / gRPC / JSON-RPC API surface.

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
| **Management Console** | Browser UI at `/console` — browse instruments by asset class, view fundamentals, action buttons for future refresh operations |

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
DUCKDB_PATH=/appdata/market-data-platform/db/market_data.duckdb   # path to the DuckDB file
HTTP_PORT=8010                   # REST API port (default: 8010)
GRPC_PORT=50060                  # gRPC port (default: 50060)
CMC_STATIC_DIR=/path/to/cmc/snapshots   # for the CMC importer
```

### 3. Run database migrations

```bash
uv run migrate
```

This creates all tables and views in the DuckDB file specified by `DUCKDB_PATH`.

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

- **Asset-class selector** — switch between crypto / equity / ETF / FX / commodity
- **Instrument list** — scrollable left pane filtered by selected class
- **Fundamentals pane** — key-value display of asset-class-specific attributes
- **Action buttons** — `BTN_UPDATE_FUNDAMENTALS` and `BTN_UPDATE_OHLCV` (stubs; logic not yet implemented)

See [docs/management-console.md](docs/management-console.md) for the full UI element reference.

---

## Database Schema

Managed via sequential SQL migrations in `src/market_data/db/migrations/`:

| Migration | Tables / Views |
|---|---|
| `001` | `instruments` |
| `002` | `instrument_identifiers` |
| `003` | `instrument_crypto` |
| `004` | `instrument_equity` |
| `005` | `instrument_etf` |
| `006` | `instrument_fx` |
| `007` | `instrument_commodity` |
| `008` | `ohlcv` |
| `009` | `ohlcv_weekly`, `ohlcv_monthly` (views) |
| `010` | `cmc_import_log`, `cmc_listing_snapshots`, `cmc_coin_tags`, `cmc_categories`, `cmc_category_coins`, `cmc_map` |
| `011` | Adds `cmc_id`, `cmc_slug`, `cmc_rank` columns to `instrument_crypto` |
| `017` | `trading_strategies` |

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
| OpenFIGI | All (reference only) | — | Free |
| SEC EDGAR | US Equities | Quarterly | Free |
| Nasdaq Data Link | Commodities, Macro | 1d | Free tier + paid |

---

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest

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
│   ├── rest/          # FastAPI routers (instruments, ohlcv, console)
│   ├── grpc/          # gRPC servicer + generated stubs
│   └── jsonrpc/       # JSON-RPC 2.0 handler
├── cli/               # CLI entry point (market-data command)
├── connectors/        # 14 data source adapters
├── db/
│   ├── migrations/    # SQL DDL files (001–011)
│   ├── connection.py  # DuckDB connection manager
│   ├── migrate.py     # Migration runner
│   └── resolver.py    # Symbol → instrument_id resolution
├── ingestion/         # Scheduler, backfill, writer, archiver
└── models/            # Pydantic models and enums
docs/
├── management-console.md
├── import-coinmarketcap-static.md
└── schema.md
proto/v1/market_data.proto
```
