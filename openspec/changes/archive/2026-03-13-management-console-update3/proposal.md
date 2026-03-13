# Proposal: Management Console Update 3

## Summary

Enrich the instrument detail view in `PANE_INSTRUMENT_LIST` with additional data: the launch date and a per-interval OHLCV data availability summary. Introduces a new `ohlcv_data_available` table that records which time intervals each data source covers. Seeds the table for two data sources: eodhd (1m/5m/1h/1d) and CoinMarketCap (1d only). Adds an eodhd entry to the `data_source` registry.

## Motivation

After "Migrate Fundamental Data" populates the instrument list, users need quick visibility into:
- When an instrument was listed (launch date)
- Which OHLCV granularities are available, and from how far back to how recently

This is diagnostic and planning information — it tells operators what data they already have ingested for each instrument across all time frames without having to query the database manually.

## Proposed Changes

### 1. DB: `ohlcv_data_available` table (new migration)

A new table that captures, per `(instrument_id, data_source_id)`, which native intervals have data. Columns:

| Column | Type | Notes |
|---|---|---|
| `instrument_id` | VARCHAR | FK → `instruments` |
| `data_source_id` | INTEGER | FK → `data_source` |
| `has_1m` | BOOLEAN DEFAULT FALSE | |
| `has_5m` | BOOLEAN DEFAULT FALSE | |
| `has_1h` | BOOLEAN DEFAULT FALSE | |
| `has_1d` | BOOLEAN DEFAULT FALSE | |

Primary key: `(instrument_id, data_source_id)`.

### 2. DB: `data_source` — new eodhd entry (new migration)

Seed a row for eodhd with:
- `name`: `EOD Historical Data`
- `short_name`: `eodhd`
- `base_url`: `https://eodhd.com`
- `api_page_url`: `https://eodhd.com/financial-apis/`
- `retrieval_priority`: `1`

### 3. DB: `ohlcv_data_available` — seed rows

After the table and eodhd data source exist, seed two template rows:

| Instrument | Data source | 1m | 5m | 1h | 1d |
|---|---|---|---|---|---|
| _(all crypto)_ | eodhd | TRUE | TRUE | TRUE | TRUE |
| _(all crypto)_ | cmc | FALSE | FALSE | FALSE | TRUE |

> **Note**: The seeding happens at migration time for all instruments currently in `instruments WHERE asset_class = 'crypto'`. The migration is idempotent (`INSERT OR IGNORE`).

### 4. API: OHLCV first/last timestamp endpoint

Expose per-instrument, per-interval availability spans from the existing `ohlcv` table and derived views. The console reads these to display the availability summary.

For native intervals (`1m`, `5m`, `1h`, `1d`) query `ohlcv` directly. For derived intervals, use the views:
- `1w` → `ohlcv_weekly`
- `4w` → `ohlcv_weekly` (4-week buckets, approximated from weekly)
- `1mth` → `ohlcv_monthly`
- `1y` and `1ytd` → computed from `1d` data

Response shape per instrument:
```json
{
  "intervals": {
    "1m":   { "first": "2024-01-01T00:00:00Z", "last": "2026-03-13T00:00:00Z" },
    "1d":   { "first": "2020-01-01T00:00:00Z", "last": "2026-03-13T00:00:00Z" },
    ...
  }
}
```
Intervals with no data are omitted from the response.

### 5. Console: instrument detail enrichment

When an instrument is selected, the console fetches and displays additional metadata below the fundamentals table:

- **Launch date** — from `instruments.launch_date` (already returned in the fundamentals API if populated, or shown as "—" if null)
- **OHLCV data available** — a compact table showing each interval alongside its first/last timestamp

### 6. Console: `ohlcv_data_available` summary in instrument detail

Below the fundamentals key-value table, render a second section "OHLCV Data Available" showing a row per `(data_source, interval)` with a ✓ or — indicator for each of 1m/5m/1h/1d.

## Out of Scope

- Actually ingesting OHLCV data from eodhd (that is a future connector task)
- Backfill or update logic for `ohlcv_data_available` rows (rows are seeded at migration time; live updates are a future ingestion concern)
- Computed intervals beyond first/last (e.g. gap detection)

## Open Questions

None.
