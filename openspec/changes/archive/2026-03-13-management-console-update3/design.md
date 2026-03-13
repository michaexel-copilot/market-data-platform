# Design: Management Console Update 3

## Overview

This change adds three layers of enrichment visible when an instrument is selected in the console:
1. Launch date (already in `instruments.launch_date`, just displayed)
2. OHLCV first/last timestamp per interval (queried live from `ohlcv` + derived views)
3. OHLCV data availability matrix (new `ohlcv_data_available` table, seeded via migration)

It also adds eodhd to the `data_source` registry and seeds the availability matrix.

## Data Layer

### New migration 015: `ohlcv_data_available`

```sql
CREATE TABLE IF NOT EXISTS ohlcv_data_available (
    instrument_id  VARCHAR  NOT NULL REFERENCES instruments(instrument_id),
    data_source_id INTEGER  NOT NULL REFERENCES data_source(data_source_id),
    has_1m         BOOLEAN  NOT NULL DEFAULT FALSE,
    has_5m         BOOLEAN  NOT NULL DEFAULT FALSE,
    has_1h         BOOLEAN  NOT NULL DEFAULT FALSE,
    has_1d         BOOLEAN  NOT NULL DEFAULT FALSE,
    PRIMARY KEY (instrument_id, data_source_id)
);
```

### New migration 016: eodhd data source + seed rows

Seeds the eodhd data source (id=2) and inserts `ohlcv_data_available` rows for all existing crypto instruments:
- eodhd: `has_1m=true, has_5m=true, has_1h=true, has_1d=true`
- cmc (id=1): `has_1d=true` only

Both use `INSERT OR IGNORE` for idempotency. New instruments added after this migration will need explicit rows inserted (future ingestion concern).

## API Layer

### New endpoint: `GET /v1/instruments/{symbol}/ohlcv-availability`

Returns first/last timestamp per interval, computed from:
- Native: `ohlcv` WHERE `interval IN ('1m','5m','1h','1d')`
- `1w` → `ohlcv_weekly` view
- `4w` → approximate from weekly (4 × 7 days, aligned to Monday)
- `1mth` → `ohlcv_monthly` view
- `1y` → `ohlcv` WHERE interval='1d', extract year span
- `1ytd` → `ohlcv` WHERE interval='1d' AND ts >= DATE_TRUNC('year', now())

Response: `{ "intervals": { "<interval>": { "first": ISO8601, "last": ISO8601 } } }`
Intervals with no rows are omitted.

Implementation: added to `instruments.py` as `GET /{symbol}/ohlcv-availability`.

## Console Layer

When an instrument is selected, two new sections appear in `PANE_FUNDAMENTALS` after the fundamentals key-value table:

### Section: OHLCV Time Range
A compact table with columns: Interval | First | Last
Populated by calling the new `/v1/instruments/{id}/ohlcv-availability` endpoint.
If no OHLCV data exists for the instrument, the section shows "No OHLCV data available".

### Section: OHLCV Data Available
A matrix table: Data Source | 1m | 5m | 1h | 1d
Populated by calling a new endpoint `GET /v1/instruments/{id}/ohlcv-data-available`.
Shows ✓ or — per cell.

The fundamentals table itself now also shows `launch_date` — it was already included in the `GET /v1/instruments/{id}/fundamentals` response (pulled from `instruments`) but may have been null. No API change needed; display logic in the console already renders all non-null fields.

## Derived Intervals

The "4w" interval is approximated: select from `ohlcv_weekly` and group into 4-week buckets aligned to the first Monday on/after the epoch. This is computed in SQL at query time. "1y" and "1ytd" are computed from `1d` rows with `DATE_TRUNC('year', ts)` grouping.

Rather than adding new views (to keep the schema simple), these are handled inline in the availability query via UNION ALL with a subquery per derived interval.

## No Breaking Changes

- No existing tables altered
- New migrations are append-only
- New API routes are additive
- Console changes are purely additive to the instrument detail panel
