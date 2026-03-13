## Context

The management console's `BTN_UPDATE_OHLCV` button currently stubs out to a `console.log`. Operators have no way to trigger data imports from locally-cached provider files. The platform already supports a `/appdata` folder convention (per the eodhd connector and `ohlcv_data_available` seeding), and the DB schema (`ohlcv`, `data_source`, `ohlcv_data_available`) is fully in place.

Two independent UX improvements are bundled here:
1. Auto-selecting Bitcoin on startup eliminates a redundant click after every page reload.
2. Making `BTN_UPDATE_OHLCV` functional allows operators to trigger local-cache imports without a command line.

## Goals / Non-Goals

**Goals:**
- Define the `/appdata/<source>/<data_class>/<interval_label>` folder convention and the mapping from intervals to folder components
- Provide `POST /v1/admin/import-ohlcv-cache` that checks the folder, parses files, upserts into `ohlcv`, and returns a structured result
- Console auto-selects the first instrument whose `ticker` equals `"BTC"` (case-insensitive) after loading the instrument list
- Console `BTN_UPDATE_OHLCV` calls the new endpoint; shows imported-row count on success and the expected folder path on folder-not-found

**Non-Goals:**
- Live file-browser or folder-management UI in the console
- Downloading data from external APIs (that is the backfill job)
- Background scheduling of cache imports
- Support for file formats beyond JSON (EODHD format) and CSV (flat columns)

## Decisions

### Decision 1: Folder path convention

```
/appdata/<source_short_name>/<data_class>/<interval_label>
```

Interval → `(data_class, interval_label)` mapping:

| Interval | data_class | interval_label |
|---|---|---|
| 1m | intraday_historical_data | 1-minute |
| 5m | intraday_historical_data | 5-minute |
| 1h | intraday_historical_data | 1-hour |
| 1d | eod_historical_data | 1-day |

The `APPDATA_DIR` root defaults to `/appdata` and is overridable via the `APPDATA_DIR` environment variable. This matches the example given in the feature spec (`/appdata/eodhd/intraday_historical_data/1-hour`).

**Alternative considered**: A flat structure `/appdata/<source>/<ticker>/<interval>`. Rejected because it deviates from the documented example path and doesn't group by data class.

### Decision 2: Best-fit source resolution is server-side

The backend resolves the best data source given `(instrument_id, interval)` by querying `ohlcv_data_available JOIN data_source` filtered by `has_<interval> = true`, ordered by `retrieval_priority ASC NULLS LAST`. This keeps source-priority logic out of the JS bundle. The request body carries only `instrument_id` and `interval`.

**Alternative considered**: Client-side resolution using the already-loaded `ohlcv-data-available` matrix. Rejected because the matrix is optional (may not load), and DB has authoritative priority values.

### Decision 3: File-to-instrument matching

The import scans all `.json` and `.csv` files in the cache folder. A file is matched to the requested instrument if its stem (filename without extension) equals `instrument_id` OR `ticker` (case-insensitive). This accommodates both slug-based names (`bitcoin.json`) and ticker-based names (`BTC.json`).

### Decision 4: Supported JSON format

Two EODHD JSON shapes are supported:
- **Intraday** (`1m`, `5m`, `1h`): array of objects with `datetime` (string `"YYYY-MM-DD HH:MM:SS"`), `open`, `high`, `low`, `close`, `volume`
- **EOD** (`1d`): array of objects with `date` (string `"YYYY-MM-DD"`), `open`, `high`, `low`, `close`, `volume`

CSV files must have header columns: `datetime` or `date`, `open`, `high`, `low`, `close`, `volume` (any order). Additional columns are ignored.

### Decision 5: Auto-select BTC in `loadInstruments`

After the instrument list is rendered, the existing `renderInstrumentList` function appends `<li>` elements with click listeners. Auto-selection triggers a programmatic `.click()` on the first `li` whose `dataset.id` matches `ticker === "BTC"` (case-insensitive) among `allLoadedInstruments`. If no BTC instrument is found, no auto-selection occurs (fail silently).

## Risks / Trade-offs

- **Large files**: A cache file may contain thousands of rows. `write_ohlcv` uses `executemany` (batched) so memory usage and latency scale with file size. A progress indicator is out of scope; the console shows a loading state on `BTN_UPDATE_OHLCV` during the call.
- **Ambiguous filenames**: If multiple files match the instrument (e.g., `bitcoin.json` and `BTC.json` both exist), all matches are imported. Duplicate rows are handled by `ON CONFLICT DO UPDATE` upsert semantics.
- **Path traversal**: The `APPDATA_DIR` root and the `source_short_name`, `data_class`, `interval_label` segments are constructed server-side from DB values (not user input), eliminating path-traversal risk.

## Migration Plan

No DB migrations required — `ohlcv`, `data_source`, and `ohlcv_data_available` are already in place from migrations 008–016. No existing API endpoints are changed (new endpoint added); no breaking changes.

Rollback: remove the new endpoint and revert the console JS handler to the stub. The ingestion module is standalone with no side effects if unused.

## Open Questions

None.
