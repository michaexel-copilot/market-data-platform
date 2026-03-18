## 1. Database Migrations

- [x] 1.1 Create `src/market_data/db/migrations_pg/023_hl_data_source.sql` — insert Hyperliquid
  into `data_source` table: `(3, 'Hyperliquid', 'hl', 'https://hyperliquid.xyz', NULL, NULL)`
  using `ON CONFLICT (data_source_id) DO NOTHING`
- [x] 1.2 Create `src/market_data/db/migrations_pg/024_instrument_source_intersection.sql` —
  create table `instrument_source_intersection(instrument_id TEXT NOT NULL REFERENCES
  instruments(instrument_id) ON DELETE CASCADE, source_short_name TEXT NOT NULL, PRIMARY KEY
  (instrument_id, source_short_name))`
- [x] 1.3 Run `uv run migrate` and confirm both migrations apply without errors

## 2. Import CLI Command

- [x] 2.1 Create `src/market_data/cli/import_source_intersection.py` — reads
  `/appdata/static_data/cc_hl_intersection.csv`, matches `base` column against
  `instruments.ticker` (case-insensitive, `asset_class = 'crypto'`), upserts one row per
  matched instrument for `source_short_name = 'eodhd'` and one for `source_short_name = 'hl'`
  using `ON CONFLICT DO NOTHING`, prints summary `matched=N, skipped=M, total=T`
- [x] 2.2 Handle missing CSV file: exit with non-zero code and clear error message
- [x] 2.3 Register the entry point in `pyproject.toml` under `[project.scripts]`:
  `import-source-intersection = "market_data.cli.import_source_intersection:main"`
- [x] 2.4 Run `uv run import-source-intersection` and verify rows are present in
  `instrument_source_intersection`

## 3. API — sources Query Parameter

- [x] 3.1 Add `sources: str | None = Query(default=None)` parameter to `list_instruments()` in
  `src/market_data/api/rest/instruments.py`
- [x] 3.2 Parse `sources` into a list of short-names by splitting on `,` and stripping
  whitespace; treat empty string as `None`
- [x] 3.3 When `sources` is provided, add a conditional JOIN block:
  ```sql
  JOIN instrument_source_intersection isi
    ON isi.instrument_id = i.instrument_id
   AND isi.source_short_name = ANY(%s)
  GROUP BY <all i columns>
  HAVING COUNT(DISTINCT isi.source_short_name) = %s
  ```
  binding the sources list and its length; apply to both the `COUNT(*)` query and the data
  query; skip the JOIN entirely when `sources` is `None`
- [x] 3.4 Verify via `curl` or the API docs at `/docs` that `?sources=eodhd,hl` returns a
  subset, `?sources=eodhd` returns a different subset, and omitting `sources` returns all

## 4. Management Console — SEG_SOURCE_FILTER Button Bar

- [x] 4.1 In `src/market_data/api/rest/console.py`, add CSS for `#SEG_SOURCE_FILTER` (same
  style as `#SEG_ASSET_CLASS`) and an `.active` state style consistent with existing button
  styles
- [x] 4.2 Add `<div id="SEG_SOURCE_FILTER">` HTML immediately after the closing tag of
  `<div id="SEG_ASSET_CLASS">`, containing four toggle buttons with `data-source` attributes:
  `eodhd` (class `active`), `hl` (class `active`), `yahoo-finance`, `cmc`
- [x] 4.3 Add a module-level JS variable `let activeSources = new Set(['eodhd', 'hl']);`
- [x] 4.4 Wire click handlers on `#SEG_SOURCE_FILTER` buttons: toggle `active` class and
  membership in `activeSources`; prevent deactivating the last active source; call
  `loadInstruments(currentClass)` after each valid toggle
- [x] 4.5 Update `loadInstruments(assetClass)` to append
  `&sources=${[...activeSources].join(',')}` to the fetch URL when `activeSources` is non-empty
- [x] 4.6 Add empty-intersection warning: when the loaded instrument list is empty and
  `activeSources.size > 0`, show "No instruments found. Run import-source-intersection to
  populate source data." in place of the blank list (reuse existing empty-state rendering path)
- [x] 4.7 Open the management console in a browser, verify default state (eodhd + hl active,
  list shows intersection), toggle sources, and confirm list updates correctly

## 5. Tests

- [x] 5.1 Add unit test in `tests/` for `import_source_intersection.py`: mock DB connection and
  CSV read, assert correct upsert calls for matched tickers and skip count for unmatched ones
- [x] 5.2 Add test case in `tests/test_api_rest.py` (or equivalent) for
  `GET /v1/instruments?sources=eodhd,hl` — seed `instrument_source_intersection` with test
  data, assert response contains only instruments in both sources
- [x] 5.3 Add test case for `?sources=` omitted — assert existing behaviour unchanged
- [x] 5.4 Run `uv run pytest` and confirm all tests pass
