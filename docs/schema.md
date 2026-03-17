# Database Schema

The platform uses [PostgreSQL 16](https://www.postgresql.org/) with the [TimescaleDB 2](https://www.timescale.com/) extension for time-series optimisation.
The connection is configured via `DATABASE_URL` in `.env`:

```
DATABASE_URL=postgresql://market_data:<password>@localhost/market_data_platform
```

Run migrations with:

```bash
uv run migrate
```

Migrations are idempotent — already-applied files are skipped. Applied files are tracked in the [`_migrations`](#_migrations) table.

The `ohlcv` and `cmc_listing_snapshots` tables are **TimescaleDB hypertables** with automatic chunk compression (ohlcv: 7-day policy). `ohlcv_weekly` and `ohlcv_monthly` are continuous aggregates that refresh automatically.

---

## Table of Contents

- [Instruments](#instruments)
  - [instruments](#instruments-1)
  - [instrument\_identifiers](#instrument_identifiers)
  - [instrument\_crypto](#instrument_crypto)
  - [instrument\_equity](#instrument_equity)
  - [instrument\_etf](#instrument_etf)
  - [instrument\_fx](#instrument_fx)
  - [instrument\_commodity](#instrument_commodity)
- [Time-Series](#time-series)
  - [ohlcv](#ohlcv)
  - [ohlcv\_weekly (view)](#ohlcv_weekly-view)
  - [ohlcv\_monthly (view)](#ohlcv_monthly-view)
- [Strategy Cache](#strategy-cache)
  - [trading\_strategies](#trading_strategies)
- [Internal](#internal)
  - [\_migrations](#_migrations)

---

## Entity Relationship

```
instruments ──┬──< instrument_identifiers
              ├──── instrument_crypto
              ├──── instrument_equity
              ├──── instrument_etf
              ├──── instrument_fx
              └──── instrument_commodity

ohlcv (no FK — instrument_id links by convention)
ohlcv_weekly  (continuous aggregate over ohlcv WHERE interval='1d')
ohlcv_monthly (continuous aggregate over ohlcv WHERE interval='1d')

trading_strategies (no FK — instrument_id links by convention)
```

Each asset-class attribute table has a **1-to-1** relationship with `instruments` (one row per instrument). `instrument_identifiers` has a **1-to-many** relationship (many external IDs per instrument).

`ohlcv` does not enforce a foreign key to `instruments` to allow ingestion to proceed independently, but `instrument_id` values are expected to match.

---

## Instruments

### instruments

Core registry. One row per tradeable instrument, regardless of asset class.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `instrument_id` | VARCHAR | NOT NULL | UUID primary key, generated at ingestion time |
| `ticker` | VARCHAR | NOT NULL | Exchange ticker symbol (e.g. `BTC`, `AAPL`) |
| `full_name` | VARCHAR | yes | Human-readable name |
| `description` | TEXT | yes | Free-text description |
| `asset_class` | VARCHAR | NOT NULL | One of: `crypto`, `equity`, `etf`, `fx`, `commodity`, `index`, `future` |
| `exchange` | VARCHAR | yes | Exchange or venue (e.g. `XNAS`, `BINANCE`) |
| `sector` | VARCHAR | yes | Sector classification (e.g. `Technology`) |
| `industry` | VARCHAR | yes | Industry classification |
| `quote_currency` | VARCHAR | yes | Currency the instrument is priced in (e.g. `USD`) |
| `launch_date` | DATE | yes | Listing or launch date |
| `is_active` | BOOLEAN | NOT NULL | `TRUE` = live; `FALSE` = delisted (soft-delete) |
| `logo_url` | VARCHAR | yes | URL to a logo image |
| `website_url` | VARCHAR | yes | Official website |
| `data_sources` | JSON | yes | JSON array of source names that provided this record |
| `first_seen_at` | TIMESTAMPTZ | NOT NULL | UTC timestamp when first ingested (default: `now()`) |
| `last_updated_at` | TIMESTAMPTZ | NOT NULL | UTC timestamp of last update (default: `now()`) |

**Indexes**
- `PRIMARY KEY (instrument_id)`
- `UNIQUE (ticker, exchange, asset_class)` — prevents duplicate listings per venue

---

### instrument_identifiers

Cross-reference table for all external IDs associated with an instrument (ISIN, FIGI, CoinGecko ID, contract addresses, etc.).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `instrument_id` | VARCHAR | NOT NULL | FK → `instruments.instrument_id` |
| `id_type` | VARCHAR | NOT NULL | One of: `isin`, `cusip`, `figi`, `composite_figi`, `mic_code`, `coingecko_id`, `cmc_id`, `coincodex_id`, `contract_address`, `ticker_exchange` |
| `id_value` | VARCHAR | NOT NULL | The identifier value |
| `chain` | VARCHAR | yes | Blockchain name — only populated when `id_type = 'contract_address'` (e.g. `ethereum`, `solana`) |

**Indexes**
- `PRIMARY KEY (instrument_id, id_type, id_value)` — deduplication; second insert for the same triple is a no-op
- `INDEX (id_type, id_value)` — fast reverse lookup (e.g. "find instrument by ISIN")

**`id_type` values**

| Value | Description |
|---|---|
| `isin` | ISO 6166 International Securities Identification Number |
| `cusip` | CUSIP (North American securities identifier) |
| `figi` | Financial Instrument Global Identifier (OpenFIGI) |
| `composite_figi` | Composite FIGI across exchanges |
| `mic_code` | ISO 10383 Market Identifier Code |
| `coingecko_id` | CoinGecko internal slug (e.g. `bitcoin`) |
| `cmc_id` | CoinMarketCap numeric ID |
| `coincodex_id` | CoinCodex slug |
| `contract_address` | On-chain contract address; use `chain` column for the network |
| `ticker_exchange` | Composite `TICKER.MIC` string used for symbol resolution (e.g. `AAPL.XNAS`) |

---

### instrument_crypto

Crypto-specific attributes. One row per crypto instrument.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `instrument_id` | VARCHAR | NOT NULL | PK + FK → `instruments.instrument_id` |
| `blockchain_network` | VARCHAR | yes | Primary blockchain (e.g. `ethereum`, `bitcoin`) |
| `consensus_mechanism` | VARCHAR | yes | e.g. `PoW`, `PoS` |
| `total_supply` | DOUBLE | yes | Total token supply |
| `max_supply` | DOUBLE | yes | Hard cap on total supply (`NULL` if unlimited) |
| `circulating_supply` | DOUBLE | yes | Current circulating supply |
| `decimals` | INTEGER | yes | Token decimal places (e.g. `18` for ERC-20) |
| `whitepaper_url` | VARCHAR | yes | URL to whitepaper |
| `github_url` | VARCHAR | yes | URL to main GitHub repository |

---

### instrument_equity

Equity-specific attributes. One row per equity instrument.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `instrument_id` | VARCHAR | NOT NULL | PK + FK → `instruments.instrument_id` |
| `isin` | VARCHAR | yes | ISIN identifier |
| `cusip` | VARCHAR | yes | CUSIP identifier |
| `figi` | VARCHAR | yes | FIGI identifier |
| `composite_figi` | VARCHAR | yes | Composite FIGI |
| `mic_code` | VARCHAR | yes | ISO 10383 MIC of primary listing venue |
| `sic_code` | VARCHAR | yes | Standard Industrial Classification code |
| `country_of_incorporation` | VARCHAR | yes | ISO 3166-1 alpha-2 country code (e.g. `US`, `DE`) |
| `shares_outstanding` | BIGINT | yes | Total shares outstanding |
| `float_shares` | BIGINT | yes | Publicly tradeable float shares |

---

### instrument_etf

ETF-specific attributes. One row per ETF instrument.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `instrument_id` | VARCHAR | NOT NULL | PK + FK → `instruments.instrument_id` |
| `tracking_index` | VARCHAR | yes | Index being tracked (e.g. `S&P 500`) |
| `expense_ratio` | DOUBLE | yes | Annual expense ratio as a decimal (e.g. `0.0003` for 0.03%) |
| `aum` | DOUBLE | yes | Assets Under Management in USD |
| `fund_type` | VARCHAR | yes | One of: `equity`, `fixed_income`, `commodity`, `mixed` |

---

### instrument_fx

FX pair attributes. One row per FX instrument.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `instrument_id` | VARCHAR | NOT NULL | PK + FK → `instruments.instrument_id` |
| `base_currency` | VARCHAR(3) | yes | ISO 4217 base currency code (e.g. `EUR`) |
| `quote_currency` | VARCHAR(3) | yes | ISO 4217 quote currency code (e.g. `USD`) |
| `pip_size` | DOUBLE | yes | Pip size (e.g. `0.0001` for EUR/USD) |
| `session_type` | VARCHAR | yes | One of: `24h` (forex round-the-clock), `regional` (exchange hours) |

---

### instrument_commodity

Commodity/futures attributes. One row per commodity instrument.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `instrument_id` | VARCHAR | NOT NULL | PK + FK → `instruments.instrument_id` |
| `unit_of_measure` | VARCHAR | yes | Trading unit (e.g. `barrel`, `troy oz`, `bushel`) |
| `contract_size` | DOUBLE | yes | Size of one contract in the stated unit |
| `delivery_month` | VARCHAR | yes | Active delivery month in `YYYY-MM` format (e.g. `2026-04`) |

---

## Time-Series

### ohlcv

All OHLCV candle data for all instruments and intervals. This is a **TimescaleDB hypertable** partitioned by `ts` (monthly chunks) with a secondary hash dimension on `instrument_id` (4 partitions). Compression is applied automatically to chunks older than 7 days.

Primary key enforces deduplication; re-ingestion of the same candle replaces the existing row (`INSERT … ON CONFLICT DO NOTHING`).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `instrument_id` | VARCHAR | NOT NULL | Links to `instruments.instrument_id` (no FK constraint) |
| `interval` | VARCHAR | NOT NULL | One of: `1m`, `5m`, `1h`, `1d` |
| `ts` | TIMESTAMPTZ | NOT NULL | Candle open timestamp in UTC |
| `open` | DOUBLE | NOT NULL | Opening price |
| `high` | DOUBLE | NOT NULL | Period high price |
| `low` | DOUBLE | NOT NULL | Period low price |
| `close` | DOUBLE | NOT NULL | Closing price |
| `volume` | DOUBLE | yes | Traded volume in base asset units |
| `vwap` | DOUBLE | yes | Volume-Weighted Average Price |
| `trade_count` | INTEGER | yes | Number of individual trades in the period |
| `market_cap` | DOUBLE | yes | Market cap at close (primarily for crypto) |
| `source` | VARCHAR | NOT NULL | Connector name that provided this candle (e.g. `coingecko`, `eodhd`) |
| `ingested_at` | TIMESTAMPTZ | NOT NULL | UTC time this row was written to the DB |

**Indexes**
- `PRIMARY KEY (instrument_id, interval, ts)`
- `INDEX (instrument_id, interval, ts)` — optimises time-range queries per instrument and interval

**Intraday archival:** `1m` and `5m` rows older than 90 days are exported to Parquet and removed from this table by the archival job (`ingestion/archiver.py`).

---

### ohlcv_weekly (continuous aggregate)

A TimescaleDB **continuous aggregate** (materialised, auto-refreshed) derived from `ohlcv WHERE interval = '1d'`. Aggregates daily candles into Monday-aligned weekly buckets using `time_bucket('1 week', ts)`.

| Column | Aggregation |
|---|---|
| `instrument_id` | group key |
| `interval` | literal `'1w'` |
| `ts` | Monday of the week (date arithmetic: `ts - ((DOW + 6) % 7) days`) |
| `open` | `first(open ORDER BY ts)` |
| `high` | `max(high)` |
| `low` | `min(low)` |
| `close` | `last(close ORDER BY ts)` |
| `volume` | `sum(volume)` |
| `vwap` | volume-weighted average: `sum(volume * vwap) / sum(volume)` |
| `trade_count` | `sum(trade_count)` |
| `market_cap` | `last(market_cap ORDER BY ts)` |
| `source` | group key |
| `ingested_at` | `max(ingested_at)` |

---

### ohlcv_monthly (continuous aggregate)

A TimescaleDB **continuous aggregate** (materialised, auto-refreshed) derived from `ohlcv WHERE interval = '1d'`. Aggregates daily candles into calendar-month buckets using `time_bucket('1 month', ts)`.

| Column | Aggregation |
|---|---|
| `instrument_id` | group key |
| `interval` | literal `'1mo'` |
| `ts` | `DATE_TRUNC('month', ts)` — first day of the calendar month |
| `open` | `first(open ORDER BY ts)` |
| `high` | `max(high)` |
| `low` | `min(low)` |
| `close` | `last(close ORDER BY ts)` |
| `volume` | `sum(volume)` |
| `vwap` | volume-weighted average |
| `trade_count` | `sum(trade_count)` |
| `market_cap` | `last(market_cap ORDER BY ts)` |
| `source` | group key |
| `ingested_at` | `max(ingested_at)` |

---

## Strategy Cache

### trading_strategies

Pre-computed indicator values produced by trading strategy algorithms. Used as a look-up cache: the REST API and `ShortDesk` read from this table rather than running live grid-search computations. Values are written by the `compute-indicators` CLI or the `POST /v1/trading-strategies/{symbol}/compute` endpoint.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `instrument_id` | VARCHAR | NOT NULL | Links to `instruments.instrument_id` (no FK constraint) |
| `strategy_name` | VARCHAR | NOT NULL | Registered strategy identifier (e.g. `best_sma`) |
| `indicator_name` | VARCHAR | NOT NULL | Name of the output indicator (e.g. `sma_low`, `sma_high`) |
| `indicator_value` | DOUBLE | NOT NULL | Computed numeric value of the indicator |
| `parameters` | TEXT | yes | JSON-encoded strategy parameters used during computation (e.g. `{"sl_short": 10, "sl_long": 10, "pos_usd": 100}`) |
| `computed_at` | TIMESTAMPTZ | NOT NULL | UTC timestamp when this row was last written (default: `now()`) |

**Indexes**
- `PRIMARY KEY (instrument_id, strategy_name, indicator_name)` — one value per indicator per strategy per instrument; re-computation UPSERTs in place

**ER relationship:**
```
trading_strategies (no FK — instrument_id links by convention to instruments.instrument_id)
```

Each `(instrument_id, strategy_name)` pair can have multiple rows — one per indicator produced by that strategy. For example, `best_sma` writes two rows per instrument: one for `sma_low` and one for `sma_high`.

---

## Internal

### _migrations

Tracks which migration files have been applied. Managed automatically by `migrate()`.

| Column | Type | Description |
|---|---|---|
| `filename` | TEXT (PK) | Migration filename (e.g. `001_instruments.sql`) |
| `applied_at` | TIMESTAMPTZ | UTC timestamp when the migration was applied |
