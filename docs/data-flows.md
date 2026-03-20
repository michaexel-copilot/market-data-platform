# Data Flow Diagrams

This document describes how data moves into, through, and out of the Market Data Platform,
with a Mermaid diagram for each major process.

---

## 1. Overall System Architecture

```mermaid
flowchart TD
    subgraph External["External Data Sources"]
        HL[Hyperliquid\nconnector]
        EODHD[EODHD\nconnector]
        CMC_API[CoinMarketCap\nAPI snapshots]
        CC_FILE[CryptoCompare\nflat files]
    end

    subgraph Ingestion["Ingestion Layer"]
        SCHED[Scheduler\nauto-ingest]
        IMP_OHLCV[import-ohlcv\nCLI]
        IMP_CMC[market-data import-cmc-static\nCLI]
        IMP_CC[import-cryptocompare\nCLI]
        BACKFILL[backfill\nCLI]
    end

    subgraph DB["PostgreSQL + TimescaleDB"]
        OHLCV[(ohlcv\nhypertable)]
        STG_CC[(stg_cryptocompare_1h\nstaging table)]
        CMC_TABLES[(CMC staging\ntables)]
        INSTRUMENTS[(instruments\ninstrument_crypto)]
        STRATEGIES[(trading_strategies)]
        AGG_W[(ohlcv_weekly\ncont. aggregate)]
        AGG_M[(ohlcv_monthly\ncont. aggregate)]
    end

    subgraph API["API Layer"]
        REST[REST API\n/v1]
        JSONRPC[JSON-RPC API\n/rpc]
        GRPC[gRPC API]
    end

    subgraph Clients["Consumers"]
        WEB[Web UI /\nShortDesk]
        SCRIPTS[Analysis scripts]
        COMPUTE[compute-indicators\nCLI]
    end

    HL --> SCHED
    EODHD --> SCHED
    EODHD --> IMP_OHLCV
    CMC_API --> IMP_CMC
    CC_FILE --> IMP_CC

    SCHED --> OHLCV
    IMP_OHLCV --> OHLCV
    BACKFILL --> OHLCV
    IMP_CMC --> CMC_TABLES
    IMP_CMC --> INSTRUMENTS
    IMP_CC --> STG_CC
    IMP_CC --> OHLCV

    OHLCV --> AGG_W
    OHLCV --> AGG_M

    OHLCV --> REST
    AGG_W --> REST
    AGG_M --> REST
    INSTRUMENTS --> REST
    CMC_TABLES --> REST
    STRATEGIES --> REST

    REST --> JSONRPC
    REST --> GRPC

    REST --> WEB
    REST --> SCRIPTS
    OHLCV --> COMPUTE
    COMPUTE --> STRATEGIES
```

---

## 2. Scheduled OHLCV Ingestion

Runs continuously via `scheduler` (or once via `ingest`).  APScheduler fires four jobs at
different frequencies; each job fetches live candles from every active connector and writes
them into the `ohlcv` hypertable.

```mermaid
flowchart TD
    START([APScheduler start])

    START --> J1["run_1m_job\nevery 1 minute"]
    START --> J2["run_5m_job\nevery 5 minutes"]
    START --> J3["run_1h_job\ntop of each hour"]
    START --> J4["run_1d_job\n00:05 UTC daily"]

    J1 --> QUERY
    J2 --> QUERY
    J3 --> QUERY
    J4 --> QUERY

    QUERY["SELECT * FROM instruments\nWHERE is_active = TRUE"]

    QUERY --> LOOP["For each instrument\n× each connector"]

    LOOP --> CONN["connector.fetch_ohlcv(\ninstrument, interval, since)"]

    CONN --> CHECK{rows\nreturned?}
    CHECK -->|No| LOOP
    CHECK -->|Yes| WRITE

    WRITE["write_ohlcv(rows)\nINSERT INTO ohlcv\nON CONFLICT DO NOTHING"]
    WRITE --> LOOP
    WRITE --> CA["TimescaleDB auto-refreshes\nohlcv_weekly / ohlcv_monthly"]
```

---

## 3. Bulk OHLCV Import from Local Cache

Used to seed historical data from EODHD cache files on disk.

```mermaid
flowchart LR
    CLI["import-ohlcv\nCLI entry point"]

    CLI -->|"POST /v1/admin/import-ohlcv"| REST["REST API\n/v1/admin/import-ohlcv"]

    REST --> HANDLER["import_ohlcv_cache.py\n_insert_file_fast()"]

    HANDLER --> DIRLIST["list cache dir\n(eodhd cache path)"]

    DIRLIST --> LOOP["For each cache file"]

    LOOP --> FMT{file\nformat?}

    FMT -->|".json"| PARSE_J["_parse_json()\nextract OHLCV rows"]
    FMT -->|".csv"| PARSE_C["_parse_csv()\nextract OHLCV rows"]

    PARSE_J --> WRITE
    PARSE_C --> WRITE

    WRITE["write_ohlcv(rows)\nINSERT INTO ohlcv\nON CONFLICT DO NOTHING"]

    WRITE --> LOOP
    LOOP -->|done| DONE([Import complete])
```

---

## 4. CoinMarketCap Static Import

Bulk-imports pre-downloaded TSV snapshot files, then promotes the latest data into the
canonical `instruments` / `instrument_crypto` tables.

```mermaid
flowchart TD
    CLI["market-data import-cmc-static [DIR]\noptional --dry-run"]

    CLI --> SCAN["Scan DIR for\n<prefix>_*_data.tsv files"]

    SCAN --> GROUP["Group files by\n<YYYY-MM-DD_HHMMSS> prefix"]

    GROUP --> LOOP["For each snapshot group"]

    LOOP --> CHECK_LOG{"snapshot_ts\nin cmc_import_log?"}
    CHECK_LOG -->|Yes, skip| LOOP
    CHECK_LOG -->|No| PARSE

    PARSE["Parse four TSV files\n(comma decimal sep,\nPython repr columns)"]

    PARSE --> LISTING["INSERT INTO\ncmc_listing_snapshots\ncmc_coin_tags"]
    PARSE --> MAP["INSERT INTO\ncmc_map"]
    PARSE --> CATS["INSERT INTO\ncmc_categories\ncmc_category_coins"]

    LISTING --> LOG
    MAP --> LOG
    CATS --> LOG

    LOG["INSERT INTO cmc_import_log\n(snapshot_ts)"]
    LOG --> LOOP
    LOOP -->|all snapshots done| ENRICH

    ENRICH["migrate_fundamentals()\nwith latest snapshot data"]

    ENRICH --> INST["UPDATE instruments\nSET full_name\nWHERE ticker = symbol\nAND asset_class = 'crypto'"]

    ENRICH --> IC["UPSERT instrument_crypto\n(cmc_id, cmc_slug, cmc_rank,\ntotal_supply, …)"]

    ENRICH --> ASM["INSERT INTO attribute_source_map\n(instrument_id, attribute_key,\nsource='cmc')"]

    ENRICH --> TSM["INSERT INTO ticker_source_map\n(cmc_id → instrument_id\nmapping)"]

    INST & IC & ASM & TSM --> DONE([Enrichment complete])
```

---

## 5. Strategy / Indicator Computation

Computes the best SMA parameters for each instrument and stores the result.

```mermaid
flowchart LR
    CLI["compute-indicators\nCLI entry point"]

    CLI -->|"POST /v1/admin/compute-indicators\n{instrument, …}"| REST["REST API\n/v1/admin/compute-indicators"]

    REST --> HANDLER["best_sma.py\ncompute_best_sma()"]

    HANDLER --> FETCH["SELECT * FROM ohlcv\nWHERE interval = '1h'\nAND instrument_id = ?"]

    FETCH --> AGG["Aggregate 1h candles\nto daily OHLCV"]

    AGG --> GRID["Grid search over\nfast_period × slow_period"]

    GRID --> EVAL["Evaluate each\n(fast, slow) pair\nby total return / drawdown"]

    EVAL --> BEST["Select best\nparameters"]

    BEST --> UPSERT["INSERT INTO trading_strategies\n… ON CONFLICT DO UPDATE"]

    UPSERT --> DONE([Done])
```

---

## 6. Historical Backfill

Fetches historical OHLCV data from a connector for a specific instrument and date range.

```mermaid
flowchart LR
    CLI["backfill\nCLI entry point"]

    CLI --> PARAMS["Resolve: connector,\ninstrument, interval,\nstart_date, end_date"]

    PARAMS --> CONN["connector.fetch_ohlcv(\ninstrument, interval,\nsince=start, until=end)"]

    CONN --> CHECK{rows\nreturned?}
    CHECK -->|No| DONE([Nothing to persist])
    CHECK -->|Yes| WRITE

    WRITE["write_ohlcv(rows)\nINSERT INTO ohlcv\nON CONFLICT DO NOTHING"]

    WRITE --> DONE([Backfill complete])
```

---

## 7. OHLCV Archival

Moves old high-frequency rows out of the live hypertable and into compressed Parquet files
to keep the database lean.

```mermaid
flowchart TD
    SCHED["Archival job\n(manual or scheduled)"]

    SCHED --> QUERY["SELECT rows FROM ohlcv\nWHERE interval IN ('1m','5m')\nAND ts < NOW() - INTERVAL '90 days'"]

    QUERY --> CHECK{rows\nfound?}
    CHECK -->|No| DONE([Nothing to archive])
    CHECK -->|Yes| WRITE_PQ

    WRITE_PQ["Write rows to\nParquet file\n(partitioned by date)"]

    WRITE_PQ --> DEL["DELETE FROM ohlcv\nWHERE interval IN ('1m','5m')\nAND ts < NOW() - INTERVAL '90 days'"]

    DEL --> DONE([Archival complete])
```

---

## 8. One-Time DuckDB Migration

One-time tool used to bootstrap the PostgreSQL database from the legacy DuckDB file.

```mermaid
flowchart LR
    CLI["migrate-from-duckdb\nCLI entry point"]

    CLI --> OPEN_D["Open DuckDB\nread-only"]
    CLI --> OPEN_P["Connect to\nPostgreSQL"]

    OPEN_D --> TABLES["List tables\nin DuckDB"]

    TABLES --> LOOP["For each table"]

    LOOP --> READ["cursor.fetchall()\nfull table scan"]

    READ --> INS["psycopg3\nexecutemany()\nINSERT … ON CONFLICT DO NOTHING"]

    INS --> LOOP

    LOOP -->|all tables copied| DONE([Migration complete])
```

---

## 9. Database Schema Summary

The following entity-relationship sketch shows how the key tables relate to each other.

```mermaid
erDiagram
    instruments {
        int instrument_id PK
        text ticker
        text full_name
        text asset_class
        bool is_active
    }
    instrument_crypto {
        int instrument_id PK,FK
        int cmc_id
        text cmc_slug
        int cmc_rank
        numeric total_supply
    }
    ohlcv {
        timestamptz ts PK
        int instrument_id PK,FK
        text interval PK
        text source PK
        double open
        double high
        double low
        double close
        double volume
    }
    ohlcv_weekly["ohlcv_weekly (cont. agg)"] {
        timestamptz week_start
        int instrument_id FK
        text source
        double open
        double high
        double low
        double close
        double volume
    }
    ohlcv_monthly["ohlcv_monthly (cont. agg)"] {
        timestamptz month_start
        int instrument_id FK
        text source
        double open
        double high
        double low
        double close
        double volume
    }
    trading_strategies {
        int instrument_id PK,FK
        text strategy_name PK
        text parameters
        double performance_metric
        timestamptz computed_at
    }
    cmc_listing_snapshots {
        timestamptz snapshot_ts PK
        int cmc_id PK
        text symbol
        numeric price_usd
        numeric market_cap_usd
        int cmc_rank
    }
    cmc_map {
        int cmc_id PK
        text slug
        text symbol
    }
    cmc_import_log {
        timestamptz snapshot_ts PK
    }

    instruments ||--o| instrument_crypto : "has crypto metadata"
    instruments ||--o{ ohlcv : "has OHLCV data"
    ohlcv ||--o{ ohlcv_weekly : "aggregated to"
    ohlcv ||--o{ ohlcv_monthly : "aggregated to"
    instruments ||--o{ trading_strategies : "has strategies"
    cmc_listing_snapshots }o--|| cmc_map : "identified by"
    cmc_listing_snapshots }o--o| cmc_import_log : "tracked by"
```

---

## 10. CryptoCompare Flat-File Import

Imports historical OHLCV data from a CryptoCompare CSV flat file into the staging table,
then promotes it to the `ohlcv` hypertable at 1h and 1d resolutions.

Three sub-commands are run in order:

```mermaid
flowchart TD
    FILE["Flat file\n/appdata/cryptocompare/1-hour/*.txt\nCSV: UNIX_TIMESTAMP, DATETIME,\nOPEN, HIGH, CLOSE, LOW,\nVOLUME_USD, VOLUME_BTC"]

    FILE --> STAGE["import-cryptocompare stage\n--instrument-id BTC-USD\n--file <path>"]

    STAGE --> TRUNC["DELETE FROM stg_cryptocompare_1h\nWHERE instrument_id = ?"]
    TRUNC --> ENSURE["_ensure_instrument()\nINSERT INTO instruments\nON CONFLICT DO NOTHING"]
    ENSURE --> BULK["executemany()\nbulk insert ~140k rows\nin batches of 5 000"]
    BULK --> STG[(stg_cryptocompare_1h\nPK: instrument_id, unix_timestamp)]

    STG --> MIGRATE["import-cryptocompare migrate\n--instrument-id BTC-USD"]
    MIGRATE --> UPSERT1["INSERT INTO ohlcv (interval='1h')\nSELECT … FROM stg_cryptocompare_1h\nON CONFLICT DO UPDATE"]
    UPSERT1 --> OHLCV[(ohlcv\nhypertable)]
    UPSERT1 --> AVAIL1["ohlcv_data_available\nhas_1h = TRUE\ndata_source_id = 4"]

    OHLCV --> AGG["import-cryptocompare aggregate-daily\n--instrument-id BTC-USD"]
    AGG --> SQL["INSERT INTO ohlcv (interval='1d')\nSELECT DATE_TRUNC('day', datetime),\nfirst(open), MAX(high), MIN(low),\nlast(close), SUM(volume_usd)\nGROUP BY day\nON CONFLICT DO UPDATE"]
    SQL --> OHLCV
    SQL --> AVAIL2["ohlcv_data_available\nhas_1d = TRUE\ndata_source_id = 4"]
```

All three commands are idempotent (truncate-per-instrument for staging; `ON CONFLICT DO UPDATE` for `ohlcv`).
