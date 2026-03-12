## Why

Financial market data is fragmented across dozens of providers with incompatible schemas, inconsistent identifiers, and different delivery mechanisms per asset class. A unified DuckDB-backed platform with a single API surface (REST/gRPC/JSON-RPC) eliminates this fragmentation — enabling downstream apps to query instruments, fundamentals, and time-series data through one contract regardless of asset class or source.

## What Changes

- Introduce a DuckDB schema covering **static/reference data** for all supported asset classes (crypto, equities, ETFs, FX, commodities) with per-asset-class attribute tables and a cross-reference identifier table
- Introduce a DuckDB schema for **dynamic OHLCV time-series data** at 1m, 5m, 1h, and 1d intervals (weekly+ as derived views); includes volume, VWAP, trade count, and market cap fields
- Define a **data source connector layer** for ingesting from CoinGecko, CoinCodex, CoinMarketCap, EODHD, Yahoo Finance, Polygon.io, Binance, Kraken, Alpha Vantage, Tiingo, FMP, OpenFIGI, SEC EDGAR, and Nasdaq Data Link
- Define a **unified API interface** exposing instrument lookup, fundamentals, and time-series over REST, gRPC, and JSON-RPC

## Capabilities

### New Capabilities

- `instrument-registry`: Static/reference data schema and model for all asset classes — instruments table, asset-class-specific attribute tables (crypto, equity, etf, fx, commodity), exchange and sector taxonomies, identifier cross-reference table (ticker, ISIN, CUSIP, FIGI, contract address)
- `time-series-ohlcv`: DuckDB schema for multi-interval OHLCV data — partitioned by asset class, instrument, and interval; 1m, 5m, 1h, 1d native; weekly/monthly as materialized views
- `data-source-connectors`: Pluggable adapter interface for each provider (CoinGecko, CoinCodex, CoinMarketCap, EODHD, Yahoo Finance, and others); handles auth, rate limiting, field mapping, and deduplication
- `unified-market-data-api`: REST, gRPC, and JSON-RPC API layer over DuckDB — instruments endpoint, OHLCV endpoint, fundamentals endpoint; consistent pagination, filtering, and symbol resolution

### Modified Capabilities

_(none — greenfield project)_

## Static Fields Model

### All asset classes (`instruments` table)
| Field | Type | Notes |
|---|---|---|
| `instrument_id` | `VARCHAR` | Internal UUID / surrogate key |
| `ticker` | `VARCHAR` | Exchange-native ticker symbol |
| `full_name` | `VARCHAR` | e.g. "Bitcoin", "Apple Inc." |
| `description` | `TEXT` | Short instrument description |
| `asset_class` | `ENUM` | `crypto`, `equity`, `etf`, `fx`, `commodity`, `index`, `future` |
| `exchange` | `VARCHAR` | Primary listing exchange |
| `sector` | `VARCHAR` | Broad sector classification |
| `industry` | `VARCHAR` | Sub-sector, more granular than sector |
| `quote_currency` | `VARCHAR` | e.g. `USD`, `BTC` |
| `launch_date` / `ipo_date` | `DATE` | Instrument inception date |
| `is_active` | `BOOLEAN` | Soft-delete / delist flag |
| `logo_url` | `VARCHAR` | For UI display |
| `website_url` | `VARCHAR` | Official site |
| `data_sources` | `JSON` | Array of provider names covering this instrument |
| `first_seen_at` | `TIMESTAMPTZ` | Audit: when first ingested |
| `last_updated_at` | `TIMESTAMPTZ` | Audit: last static data refresh |

### Identifier cross-reference (`instrument_identifiers` table)
| Field | Type | Notes |
|---|---|---|
| `instrument_id` | `VARCHAR` | FK → instruments |
| `id_type` | `ENUM` | `isin`, `cusip`, `figi`, `composite_figi`, `mic_code`, `coingecko_id`, `cmc_id`, `coincodex_id`, `contract_address`, `ticker_exchange` |
| `id_value` | `VARCHAR` | The identifier value |
| `chain` | `VARCHAR` | For `contract_address`: blockchain name (e.g. `ethereum`) |

### Crypto-specific (`instrument_crypto` table)
| Field | Type | Notes |
|---|---|---|
| `instrument_id` | `VARCHAR` | FK → instruments |
| `blockchain_network` | `VARCHAR` | e.g. `ethereum`, `solana`, `bitcoin` |
| `consensus_mechanism` | `VARCHAR` | `PoW`, `PoS`, `DPoS`, etc. |
| `total_supply` | `DOUBLE` | Hard cap or current total |
| `max_supply` | `DOUBLE` | Absolute max (null if uncapped) |
| `circulating_supply` | `DOUBLE` | Updated daily |
| `decimals` | `INTEGER` | Token divisibility |
| `whitepaper_url` | `VARCHAR` | |
| `github_url` | `VARCHAR` | |

### Equity-specific (`instrument_equity` table)
| Field | Type | Notes |
|---|---|---|
| `instrument_id` | `VARCHAR` | FK → instruments |
| `isin` | `VARCHAR` | International identifier |
| `cusip` | `VARCHAR` | US identifier |
| `figi` | `VARCHAR` | OpenFIGI identifier |
| `composite_figi` | `VARCHAR` | |
| `mic_code` | `VARCHAR` | ISO MIC (e.g. `XNAS`, `XNYS`) |
| `sic_code` | `VARCHAR` | US industry classification |
| `country_of_incorporation` | `CHAR(2)` | ISO 3166-1 alpha-2 |
| `shares_outstanding` | `BIGINT` | Updated quarterly |
| `float_shares` | `BIGINT` | |

### ETF-specific (`instrument_etf` table)
| Field | Type | Notes |
|---|---|---|
| `instrument_id` | `VARCHAR` | FK → instruments |
| `tracking_index` | `VARCHAR` | e.g. `S&P 500` |
| `expense_ratio` | `DOUBLE` | Annual % |
| `aum` | `DOUBLE` | Assets under management (USD) |
| `fund_type` | `VARCHAR` | `equity`, `fixed_income`, `commodity`, `mixed` |

### FX-specific (`instrument_fx` table)
| Field | Type | Notes |
|---|---|---|
| `instrument_id` | `VARCHAR` | FK → instruments |
| `base_currency` | `CHAR(3)` | e.g. `EUR` |
| `quote_currency` | `CHAR(3)` | e.g. `USD` |
| `pip_size` | `DOUBLE` | Minimum price movement |
| `session_type` | `VARCHAR` | `24h`, `regional` |

### Commodity-specific (`instrument_commodity` table)
| Field | Type | Notes |
|---|---|---|
| `instrument_id` | `VARCHAR` | FK → instruments |
| `unit_of_measure` | `VARCHAR` | e.g. `barrel`, `troy oz`, `bushel` |
| `contract_size` | `DOUBLE` | For futures |
| `delivery_month` | `VARCHAR` | Front-month label (e.g. `2026-04`) |

---

## Impact

- **DuckDB**: Primary storage engine for both static and dynamic data; relies on DuckDB's columnar compression and Parquet compatibility for efficient time-series storage
- **Python service**: API layer (FastAPI for REST + JSON-RPC, grpcio for gRPC); ingestion scheduler (APScheduler or similar)
- **No breaking changes** — net-new system

### Data Sources

| Source | Asset Classes | Intervals | Cost | Role |
|---|---|---|---|---|
| **CoinGecko** | Crypto | 1d (intraday on paid) | Free tier + paid | Primary crypto fundamentals + OHLCV; 10k+ coins; stable IDs |
| **CoinCodex** | Crypto | 1d | Free | Supplemental crypto; price predictions |
| **CoinMarketCap** | Crypto | 1d, 1h (paid), 5m (paid) | Free tier + paid | Industry-standard crypto IDs; market cap rankings |
| **EODHD** | Equities, ETFs, FX, Crypto, Indices, Futures | 1m, 5m, 1h, 1d | Paid (all-world subscription) | Primary all-world OHLCV + fundamentals; splits; dividends |
| **Yahoo Finance** (`yfinance`) | Equities, ETFs, FX, Crypto, Futures | 1m (7d), 5m, 1h, 1d | Free (unofficial) | Fallback/backfill; backtesting; limited sub-daily history |
| **Polygon.io** | US Equities, ETFs, FX, Crypto | 1s, 1m, 5m, 1h, 1d | Free tier + paid | WebSocket real-time; official exchange feeds; US equities primary |
| **Alpha Vantage** | Equities, FX, Crypto, Commodities | 1m, 5m, 15m, 30m, 1h, 1d | Free (rate limited) | Free fallback for equities + FX |
| **Tiingo** | US Equities, ETFs, FX, Crypto | 1m, 1h, 1d | Free tier + paid | IEX intraday feed; affordable; clean API |
| **Financial Modeling Prep (FMP)** | Equities, ETFs, Crypto, FX | 1m, 5m, 1h, 1d | Free tier + paid | Rich fundamentals (income stmt, balance sheet) for static enrichment |
| **Binance Public API** | Crypto | 1m, 5m, 1h, 1d, 1w | Free | Direct exchange feed; most liquid pairs; no key required |
| **Kraken API** | Crypto | 1m, 5m, 1h, 1d | Free | BTC/ETH data; EU regulatory compliance |
| **OpenFIGI** (Bloomberg) | All | N/A (reference only) | Free | Maps tickers ↔ ISIN ↔ FIGI ↔ CUSIP; identifier cross-referencing |
| **SEC EDGAR** | US Equities | Quarterly | Free | Official US fundamentals; earnings; filings; pairs with EODHD |
| **Nasdaq Data Link (Quandl)** | Commodities, Macro | 1d | Free tier + paid | Commodities, futures, macro series (FRED-compatible) |

### Source-to-asset-class matrix

| Asset Class | Primary OHLCV | Secondary / Fallback | Fundamentals / Reference |
|---|---|---|---|
| Crypto | CoinGecko, Binance | CoinMarketCap, Kraken | CoinGecko, CoinCodex, CMC |
| US Equities | EODHD, Polygon.io | Tiingo, Yahoo Finance | FMP, SEC EDGAR, OpenFIGI |
| Global Equities | EODHD | Yahoo Finance, Alpha Vantage | FMP, EODHD, OpenFIGI |
| ETFs | EODHD | Yahoo Finance, Tiingo | FMP, EODHD |
| FX | EODHD | Alpha Vantage, Tiingo | — |
| Commodities | EODHD | Nasdaq Data Link | Nasdaq Data Link |
| Indices | EODHD | Yahoo Finance | EODHD |
