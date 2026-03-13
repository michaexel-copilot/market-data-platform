## 1. Ingestion: OHLCV cache importer module

- [x] 1.1 Create `src/market_data/ingestion/import_ohlcv_cache.py` with interval → `(data_class, interval_label)` mapping dict and `get_cache_path(source_short_name, interval) -> Path` helper (uses `APPDATA_DIR` env var, defaults to `/appdata`)
- [x] 1.2 Implement `_find_matching_files(folder: Path, instrument_id: str, ticker: str) -> list[Path]` — scans `.json` and `.csv` files; matches stem against `instrument_id` and `ticker` case-insensitively
- [x] 1.3 Implement `_parse_json(path: Path, instrument_id: str, interval: str, source: str) -> list[OHLCVRecord]` — supports intraday (`datetime`) and EOD (`date`) shapes; timestamps parsed as UTC
- [x] 1.4 Implement `_parse_csv(path: Path, instrument_id: str, interval: str, source: str) -> list[OHLCVRecord]` — header-based column detection; same timestamp rules
- [x] 1.5 Implement `import_from_cache(instrument_id: str, ticker: str, source_short_name: str, interval: str, conn) -> dict` — orchestrates path resolution, folder check, file matching, parsing, and `write_ohlcv()` call; returns `{status, rows_imported, files_processed}` or `{status: "folder_not_found", expected_path}`

## 2. API: import-ohlcv-cache endpoint

- [x] 2.1 Define Pydantic request model `ImportOhlcvCacheRequest(instrument_id: str, interval: str)` in `admin.py`
- [x] 2.2 Add `POST /v1/admin/import-ohlcv-cache` to `src/market_data/api/rest/admin.py` — queries `ohlcv_data_available JOIN data_source` for best-fit source (filtered by `has_<interval>`, ordered by `retrieval_priority ASC NULLS LAST`); fetches `ticker` from `instruments`; calls `import_from_cache`; returns structured result; returns HTTP 422 if no eligible source found

## 3. Console: auto-select Bitcoin on startup

- [x] 3.1 In `src/market_data/api/rest/console.py`, update `loadInstruments` to auto-select the first instrument with `ticker === "BTC"` (case-insensitive) after `renderInstrumentList` by finding its `<li>` element in `INSTRUMENT_LIST_UL` and calling `.click()` on it

## 4. Console: BTN_UPDATE_OHLCV real handler

- [x] 4.1 Replace the `BTN_UPDATE_OHLCV` stub click handler in `console.py` with a real async handler: set button to disabled/`"Importing…"` state; call `POST /v1/admin/import-ohlcv-cache` with `{instrument_id: selectedInstrumentId, interval: ddlPeriod.value}`; restore button state after completion
- [x] 4.2 On `status === "ok"`: prepend an inline success message `"Imported N rows from cache."` to the fundamentals pane and re-fetch OHLCV availability and matrix sections for the current instrument
- [x] 4.3 On `status === "folder_not_found"`: show inline error `"Cache folder not found. Expected: <expected_path>"` in the fundamentals pane without replacing the current fundamentals content
- [x] 4.4 On any HTTP/network error: show `"OHLCV import failed: <message>"` in the fundamentals pane
