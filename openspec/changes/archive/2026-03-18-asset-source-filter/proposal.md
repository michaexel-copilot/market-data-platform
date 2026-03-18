## Why

The management console instrument list shows all registered instruments regardless of whether
any data source actually has OHLCV data for them, making it impossible to know which assets
can be charted or analysed. Users need to filter the list by data source (e.g. show only
instruments available on both EODHD and Hyperliquid) and see their intersection when multiple
sources are selected.

## What Changes

- Add a new database table `instrument_source_intersection` that stores, for each instrument,
  the set of data source short-names it belongs to (e.g. `["eodhd", "hl"]`)
- Add a one-shot CLI command `uv run import-source-intersection` that seeds the table from
  the pre-computed CSV at `/appdata/static_data/cc_hl_intersection.csv` (columns: `base`,
  `eodhd_code`, `hl_symbol`)
- Extend `GET /v1/instruments` with an optional `?sources=<csv>` query parameter
  (e.g. `?sources=eodhd,hl`) that filters results to instruments present in **all** specified
  sources; no change when the parameter is omitted
- Add a data-source filter button bar to the management console as a second row in the header:
  buttons **eodhd** (default ON), **hyperliquid** (default ON), **yahoo-finance** (default OFF),
  **cmc** (default OFF); toggling a button reloads the instrument list via HTMX with the
  matching `?sources=` value

## Capabilities

### New Capabilities

- `asset-source-intersection`: Database table `instrument_source_intersection`, its migration,
  and the `import-source-intersection` CLI command that seeds it from the static CSV.
  Covers schema, upsert logic, and idempotent re-seeding.

### Modified Capabilities

- `unified-market-data-api`: New optional `sources` query parameter on
  `GET /v1/instruments` — filters by intersection of specified data source short-names using
  the `instrument_source_intersection` table. Existing query parameters and response shape
  are unchanged.
- `management-console`: New data-source filter button bar (second header row). Default
  selection is eodhd + hyperliquid. Button state drives the `?sources=` parameter on all
  instrument list requests. Behaviour of existing asset-class selector, text filter, and
  fundamentals pane is unchanged.

## Impact

- **New migration**: `src/market_data/db/migrations_pg/023_instrument_source_intersection.sql`
- **New CLI entry point**: `import-source-intersection` in `pyproject.toml`
- **API**: Non-breaking — `?sources=` is optional; existing clients unaffected
- **Frontend**: Management console HTML template gains one `btn-group` row and updated HTMX
  attribute on the instrument list fetch
- **Data dependency**: `/appdata/static_data/cc_hl_intersection.csv` must exist before
  running `import-source-intersection`; EODHD-only asset list is out of scope (deferred)
- **No dependency changes**: No new Python packages required
