# CoinMarketCap Static Data Importer

Batch import of pre-downloaded CoinMarketCap TSV snapshot files into the DuckDB database.

## Overview

The importer reads historical snapshots downloaded from the CoinMarketCap API and stored as
TSV files on disk.  It is **idempotent** — running it multiple times on the same directory
is safe.

## File Patterns

Each snapshot set consists of four files sharing a `<YYYY-MM-DD_HHMMSS>` prefix:

| Pattern | Content |
|---------|---------|
| `<prefix>_listing_data.tsv` | Per-coin price, market-cap, supply, and rank at snapshot time |
| `<prefix>_map_data.tsv` | Canonical CMC id ↔ slug mapping with history date range |
| `<prefix>_categories_data.tsv` | Category master records (id, title, stats) |
| `<prefix>_category_data.tsv` | Per-category coin associations (one coin per row) |

Numeric columns use a **comma** as the decimal separator (European locale).  The `tags`
column in `listing_data` is a Python list repr (`['tag1', 'tag2']`).  The `coins` column
in `category_data` is a Python dict repr for a single coin per row.

## Database Tables

After running migrations the following tables are available:

| Table | Primary Key | Description |
|-------|-------------|-------------|
| `cmc_import_log` | `snapshot_ts` | Tracks fully-imported snapshots |
| `cmc_listing_snapshots` | `(snapshot_ts, cmc_id)` | Price/market-cap snapshot per coin |
| `cmc_coin_tags` | `(cmc_id, tag)` | Normalised tag associations |
| `cmc_categories` | `cmc_id` | Category master data |
| `cmc_category_coins` | `(category_id, cmc_coin_id)` | Category ↔ coin associations |
| `cmc_map` | `cmc_id` | Canonical coin ↔ CMC id mapping |

The `instrument_crypto` table gains three nullable columns populated by the enrichment step:

| Column | Type | Description |
|--------|------|-------------|
| `cmc_id` | `INTEGER` | CoinMarketCap numeric id |
| `cmc_slug` | `VARCHAR` | CMC URL slug (matches `cmc_map.slug`) |
| `cmc_rank` | `INTEGER` | CMC market-cap rank at time of last import |

## CLI Usage

```bash
# Import from a specific directory
market-data import-cmc-static /mnt/ds420/data/krypto/coinmarketcap/01_download

# Use the CMC_STATIC_DIR environment variable
export CMC_STATIC_DIR=/mnt/ds420/data/krypto/coinmarketcap/01_download
market-data import-cmc-static

# Parse and validate files without writing to the database
market-data import-cmc-static /path/to/data --dry-run
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CMC_STATIC_DIR` | — | Default snapshot directory (used if no `DIR` argument is given) |
| `DUCKDB_PATH` | `/appdata/market-data-platform/db/market_data.duckdb` | Path to the DuckDB database file |

## Idempotency

Snapshot timestamps are recorded in `cmc_import_log` after successful ingestion.  
Re-running the importer on the same directory skips already-processed snapshots.  
To force a re-import, delete the relevant rows from `cmc_import_log`:

```sql
DELETE FROM cmc_import_log WHERE snapshot_ts = '2025-08-05 11:12:20+00';
```

## Enrichment

After all snapshots are processed, the importer updates `instrument_crypto` rows where
`instrument_id` (slug) matches a `cmc_map.slug`.  This enriches existing instruments with
their CoinMarketCap id and rank without creating new instrument records.

## Error Handling

- Row-level parse errors are logged at `WARNING` level and skipped; the import continues.
- Missing sibling files for a snapshot are logged as `WARNING`; the available files are
  still imported.
- The import can be safely interrupted and re-run; only fully-processed snapshots are
  recorded in `cmc_import_log`.

## Python API

```python
from pathlib import Path
from market_data.ingestion.import_coinmarketcap_static import run_import

counts = run_import(
    directory=Path("/mnt/ds420/data/krypto/coinmarketcap/01_download"),
    dry_run=False,          # set True to preview without writing
    progress_interval=100,  # log INFO every N snapshots
)
print(counts)
# {'listing': 4972000, 'map': 9446, 'categories': 30, 'category_coins': 101, 'skipped': 0}
```
