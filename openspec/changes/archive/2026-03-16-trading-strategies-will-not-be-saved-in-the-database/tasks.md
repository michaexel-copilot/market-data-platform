## 1. REST Endpoint: POST /v1/admin/import-ohlcv

- [x] 1.1 Add `ImportOhlcvRequest` Pydantic model to `admin.py` (fields: `interval: str`, `symbol: str | None`)
- [x] 1.2 Implement `POST /v1/admin/import-ohlcv` endpoint in `admin.py` — bulk loop over active instruments, call `import_from_cache` per instrument with `source_short_name="eodhd"`, return `{ok, errors, results}`
- [x] 1.3 Handle single-symbol case: resolve via `resolve_symbol`, return HTTP 404 if not found

## 2. CLI: import-ohlcv

- [x] 2.1 Create `src/market_data/cli/import_ohlcv.py` with `main()` — build payload, POST to `/v1/admin/import-ohlcv`, print per-ticker status lines, exit with code 1 if any errors
- [x] 2.2 Register `import-ohlcv = "market_data.cli.import_ohlcv:main"` in `pyproject.toml`

## 3. Strategy Engine: 1h → daily aggregation

- [x] 3.1 Update `compute_best_sma` in `best_sma.py` — replace `WHERE interval='1d'` query with a CTE that aggregates `1h` rows to daily bars (open=first, high=max, low=min, close=last, volume=sum grouped by `DATE_TRUNC('day', ts)`)
- [x] 3.2 Update error message to say `interval='1h'` instead of `interval='1d'`

## 4. ShortDesk: remove local cache

- [x] 4.1 Remove `_BEST_SMA_CACHE`, `_BEST_SMA_CACHE_DIR`, `_best_sma_cache_path`, `_load_best_sma_cache`, `_save_best_sma_cache`, `_find_best_sma` from `web.py`
- [x] 4.2 Simplify `best_sma_endpoint` to call market-data-platform API only; return HTTP 503 if the API returns 404 (no precomputed data)

## 5. Tests

- [x] 5.1 Add/update test in `test_strategies.py` — use `1h` fixture data and verify `compute_best_sma` aggregates correctly and returns valid pair
- [x] 5.2 Add test for `POST /v1/admin/import-ohlcv` in `test_api_rest.py` — mock import call, verify response shape
- [x] 5.3 Run full test suite and confirm all pass
