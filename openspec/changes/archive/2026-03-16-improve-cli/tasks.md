## 1. REST Endpoints — compute-indicators

- [x] 1.1 Add `ComputeIndicatorsRequest` Pydantic model to `admin.py` with fields: `strategy: str`, `symbol: str | None`, `sl_short: float = 10.0`, `sl_long: float = 10.0`, `pos_usd: float = 100.0`
- [x] 1.2 Add `POST /v1/admin/compute-indicators` route handler in `admin.py` that resolves symbol if given, iterates active instruments, runs strategy, collects per-instrument results, and returns the counts + results list
- [x] 1.3 Ensure the handler is a plain `def` (not `async def`) so FastAPI dispatches it to the thread pool

## 2. REST Endpoints — import-cmc-static

- [x] 2.1 Add `ImportCmcStaticRequest` Pydantic model to `admin.py` with field: `dir: str | None = None`
- [x] 2.2 Add `POST /v1/admin/import-cmc-static` route handler in `admin.py` that resolves the directory (body `dir` → `CMC_STATIC_DIR` env → error), validates it exists, calls `run_import()`, and returns counts
- [x] 2.3 Return HTTP 422 with a clear error message when no directory is configured or directory does not exist

## 3. CLI — compute-indicators

- [x] 3.1 Rewrite `src/market_data/cli/compute_indicators.py` to use `httpx` instead of DuckDB: build request body from CLI args, POST to `{base_url}/v1/admin/compute-indicators`, print results, exit with correct code
- [x] 3.2 Add `--url` / `MARKET_DATA_URL` support with default `http://localhost:8010`
- [x] 3.3 Print per-instrument results in the same format as the old CLI (ticker + OK/ERROR + elapsed)
- [x] 3.4 Exit 1 if `errors > 0` or if the HTTP request fails; exit 0 otherwise

## 4. CLI — market-data import-cmc-static

- [x] 4.1 Rewrite the `import-cmc-static` sub-command in `src/market_data/cli/__init__.py` to use `httpx`: POST to `{base_url}/v1/admin/import-cmc-static`, print counts, handle errors
- [x] 4.2 Remove `--dry-run` flag (not supported by REST endpoint)
- [x] 4.3 Add `--url` / `MARKET_DATA_URL` support with default `http://localhost:8010`

## 5. Tests

- [x] 5.1 Update `tests/test_cli_compute_indicators.py` to mock `httpx` instead of DuckDB; assert correct URL, body, and output
- [x] 5.2 Add tests for the new `POST /v1/admin/compute-indicators` endpoint (success bulk, success single, unknown strategy, unknown symbol, partial errors)
- [x] 5.3 Add tests for the new `POST /v1/admin/import-cmc-static` endpoint (success, missing dir, dir not found)

## 6. Documentation

- [x] 6.1 Add an "Admin Endpoints" section to `docs/management-console.md` documenting `POST /v1/admin/compute-indicators` and `POST /v1/admin/import-cmc-static` with request/response examples
- [x] 6.2 Add CLI invocation examples in the same section showing `compute-indicators` and `market-data import-cmc-static` usage
