## Context

The platform stores crypto instrument metadata and OHLCV time-series in DuckDB.  An archive
of ~4 972 CoinMarketCap snapshot sets (TSV, dating from August 2025) sits on
`/mnt/ds420/data/krypto/coinmarketcap/01_download` and is currently not ingested.  The
existing `CoinMarketCapConnector` only fetches live OHLCV from the API.

Each snapshot set consists of four TSV files sharing a `<date>_<time>` prefix:

| Pattern | Typical rows | Key content |
|---------|-------------|-------------|
| `listing_data` | ~1 000 | Price, volume, market-cap, supply, rank per coin |
| `map_data` | ~9 000 | Canonical coin ↔ CMC-id mapping with activity dates |
| `categories_data` | ~30 | Category master records (id, title, stats) |
| `category_data` | ~100 | Per-category rows each containing a JSON array of coins |

Decimal separator in numeric columns is a **comma** (European locale).  String lists (tags)
are stored as Python-repr list literals (`['mineable', 'pow', ...]`).  The `category_data`
`coins` column contains full Python-dict repr for each coin.

Constraints:
- DuckDB is the single storage layer; no ORM.
- Migrations run via `src/market_data/db/migrate.py` (alphabetical `.sql` files).
- Existing `instrument_crypto` table uses `instrument_id` (slug-based) as PK.
- The importer must be **idempotent** — safe to re-run on an already-imported directory.
- No new third-party packages (stdlib + `duckdb` only).

## Goals / Non-Goals

**Goals:**
- Ingest all four TSV file types into purpose-built DuckDB tables.
- Enrich `instrument_crypto` with CMC-specific nullable columns.
- Populate a normalised `cmc_coin_tags` table from the listing tags column.
- Expose a CLI entry-point `market-data import-cmc-static <dir>`.
- Be fully idempotent; duplicate runs must not insert duplicates.
- Produce progress logging at INFO level; errors at WARNING/ERROR.

**Non-Goals:**
- Real-time or scheduled ingestion of live CMC API data (existing connector handles this).
- Ingestion of OHLCV price history from listing snapshots (those belong in `ohlcv` table,
  handled separately if needed).
- Backfilling `ohlcv` from listing snapshot prices.
- Normalising the `coins` JSON blobs inside `category_data` into `instrument_crypto`.

## Decisions

### D1 — Separate CMC snapshot tables, not folded into `ohlcv`

The listing snapshots capture a richer set of attributes (rank, supply, dominance, tags)
than the OHLCV schema allows.  Folding them into `ohlcv` would require nullable/ignored
columns and confuse the time-series semantics.

*Alternative considered*: Extend `ohlcv` with extra nullable columns.  Rejected because it
violates the separation between price time-series and reference/metadata data.

**New tables:**
- `cmc_listing_snapshots(snapshot_ts, cmc_id, ...)` — PK `(snapshot_ts, cmc_id)`
- `cmc_coin_tags(cmc_id, tag)` — PK `(cmc_id, tag)` (static; last-write wins)
- `cmc_categories(cmc_id TEXT, ...)` — PK `cmc_id`
- `cmc_category_coins(category_id, cmc_coin_id)` — PK `(category_id, cmc_coin_id)`
- `cmc_map(cmc_id, ...)` — PK `cmc_id`

### D2 — Idempotency via `INSERT … ON CONFLICT DO NOTHING`

All tables use natural composite PKs.  Re-importing a directory that was already processed
produces zero new rows.  A `cmc_import_log` table records which snapshot timestamps have
been fully processed, allowing the importer to skip already-complete snapshots cheaply.

*Alternative*: File-path hash in an import log.  Rejected because the snapshot timestamp is
already a natural idempotency key and is meaningful metadata.

### D3 — File discovery by glob pattern, not hardcoded paths

The importer accepts a `--dir` argument (default from env `CMC_STATIC_DIR`).  It globs for
`*_listing_data.tsv` to discover snapshot timestamps, then derives sibling file paths.
Missing sibling files are logged as warnings and skipped (partial snapshots are tolerated).

### D4 — stdlib `csv.DictReader` for TSV parsing

The files are plain TSV.  `csv.DictReader(f, delimiter='\t')` is sufficient and avoids a
pandas dependency.  Numeric columns are normalised inline (replace `,` with `.`, cast to
float).

*Alternative*: DuckDB `read_csv_auto()`.  Makes decimal normalisation harder and gives less
control over error rows.  Rejected.

### D5 — Two new migration files, not ALTER TABLE on existing migrations

`010_cmc_static_tables.sql` — creates all five CMC snapshot tables.
`011_instrument_crypto_cmc_columns.sql` — adds nullable `cmc_id INTEGER`, `cmc_slug
VARCHAR`, `cmc_rank INTEGER` to `instrument_crypto` via `ALTER TABLE … ADD COLUMN IF NOT
EXISTS`.

This keeps existing migrations immutable.

### D6 — CLI wired via `typer` app in `src/market_data/cli/__init__.py`

A lightweight `typer` CLI (already implied by the project structure) exposes:

```
market-data import-cmc-static [DIR]
```

`DIR` defaults to the env variable `CMC_STATIC_DIR`.  Implemented in
`src/market_data/ingestion/import_coinmarketcap_static.py`; the CLI module just imports and
delegates.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Comma decimal separator breaks float parsing | Normalise with `str.replace(',', '.')` before `float()` |
| `category_data` coins column is Python `repr`, not JSON | Use `ast.literal_eval` (safe stdlib eval for dicts/lists) |
| ~5 M listing rows → long initial import | Progress bar via `logging` every 100 snapshots; can be re-run with `--dry-run` |
| Future schema changes in source files | Importer uses dict-key access with `.get()` and logs unknown/missing columns as warnings |
| `instrument_crypto` enrichment may resolve wrong coin if symbols collide | Enrich only where `(symbol, slug)` matches; log ambiguous cases |

## Migration Plan

1. Run `migrate()` — applies `010_cmc_static_tables.sql` and
   `011_instrument_crypto_cmc_columns.sql` automatically.
2. Run `market-data import-cmc-static /mnt/ds420/data/krypto/coinmarketcap/01_download` —
   idempotent, safe to interrupt and re-run.
3. No rollback required for reads.  To roll back: `DROP TABLE cmc_*; DROP TABLE
   cmc_import_log;` and re-apply migration.

## Open Questions

- Should `cmc_listing_snapshots` store price/volume data from `listing_data` (currently
  scoped out as non-goal)?  If yes, the table schema needs `price`, `volume_24h`, etc.
  Deferred to a follow-up change.
- Should the importer also try to match `cmc_map` entries to `instruments` and auto-create
  missing `instrument_crypto` rows?  Currently out of scope to avoid creating unvalidated
  instruments.
