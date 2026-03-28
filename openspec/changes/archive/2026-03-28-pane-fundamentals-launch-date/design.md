## Context

The `instruments` base table defines a nullable `launch_date DATE` column intended to record the listing or genesis date of an asset. For crypto instruments, CoinMarketCap's `cmc_map` table already stores `first_historical_data TIMESTAMPTZ` — the earliest date for which CMC holds price data — which is a reliable proxy for the consensus launch date of a coin.

Currently, the `migrate_fundamentals` enrichment step populates `cmc_id`, `cmc_slug`, and `cmc_rank` from `cmc_map` into `instrument_crypto`, but does not write `launch_date` into the base `instruments` table. The fundamentals API only queries the asset-class-specific table and omits all `instruments` base fields from the response, so even existing `launch_date` values are invisible to the console.

## Goals / Non-Goals

**Goals:**
- Write `instruments.launch_date` from `cmc_map.first_historical_data::DATE` during the enrich step.
- Return `launch_date` as part of the `GET /v1/instruments/{symbol}/fundamentals` response.
- Render a "Launch Date" row in `PANE_FUNDAMENTALS` displaying `YYYY-MM-DD` (omit row if null).

**Non-Goals:**
- Populating `launch_date` for non-crypto asset classes (no data source available yet).
- Adding a dedicated migration endpoint for back-filling already-stored instruments (the existing `BTN_UPDATE_FUNDAMENTALS` re-runs migrate_fundamentals, which is enough).
- Schema changes — `launch_date DATE` already exists on `instruments`.

## Decisions

### Pull date from `cmc_listing_snapshots.date_added`, not `cmc_map.first_historical_data`
`cmc_listing_snapshots` is populated by the CMC import and contains a `date_added` column — the date CMC first listed the coin. `cmc_map` is a separate table populated only when `map_data.tsv` files are imported; it may be empty if only `listing_data.tsv` snapshots have been ingested. Using `date_added` from the listing snapshot therefore works in all real deployments and requires no additional data import.

**Alternatives considered:** `cmc_map.first_historical_data` — appropriate in theory but not available when `cmc_map` is empty (which is the common state in this project). `date_added` from `cmc_listing_snapshots` is always present alongside the other CMC enrichment data and represents the same semantic value (the coin's public listing date).

### Include `launch_date` in the fundamentals API response (not a separate endpoint)
The console populates `PANE_FUNDAMENTALS` with a single call to `GET /v1/instruments/{symbol}/fundamentals`. Returning `launch_date` alongside the other base fields keeps the rendering simple with no additional round-trips.

**Alternatives considered:** A separate `GET /v1/instruments/{symbol}/base` endpoint — unnecessary complexity for a single field addition.

### Join `instruments` in `get_fundamentals()` to retrieve base fields
The fundamentals handler builds a response dict already keyed by asset class. Adding a second `SELECT launch_date FROM instruments WHERE instrument_id = %s` (or including it in the existing `SELECT instrument_id, asset_class FROM instruments …` row) retrieves the date without a structural change to the response shape.

## Risks / Trade-offs

- **`cmc_map` only matches slugs, not all symbols** — instruments ingested from other sources without a matching CMC slug will have `launch_date = NULL`. The UI handles this gracefully by omitting the row when null.
- **`first_historical_data` is a proxy, not a canonical genesis date** — for some coins, CMC's data starts later than actual launch. Acceptable trade-off given no better structured source.
- **`ON CONFLICT DO UPDATE` with `launch_date`** — the enrich step must not overwrite a non-null `launch_date` with NULL (e.g. if a coin disappears from `cmc_map`). Fix: use `COALESCE` or skip update when `cmc_map.first_historical_data IS NULL`.

## Migration Plan

1. Deploy updated `migrate_fundamentals.py` — next run of `BTN_UPDATE_FUNDAMENTALS` will populate `launch_date` for all matched crypto instruments.
2. No database migration required.
3. Rollback: revert code change; `launch_date` column remains in schema with `NULL` values — no functional regression.

## Open Questions

_(none)_
