## Context

The platform exposes a REST API (FastAPI / uvicorn on port 8010) backed by a single
DuckDB file.  DuckDB allows multiple readers but only one writer at a time.  When the
REST service holds the write connection, any CLI that tries to open its own connection
with `get_connection()` is immediately blocked with *"database is locked"*.

Currently two CLIs bypass the API layer:
- `compute-indicators` (`src/market_data/cli/compute_indicators.py`) — bulk-runs a
  strategy and writes results to `trading_strategies`.
- `market-data import-cmc-static` (`src/market_data/cli/__init__.py`) — imports
  CoinMarketCap TSV snapshots.

Both are the only entry points for those operations; neither has a matching REST
endpoint.

## Goals / Non-Goals

**Goals:**
- Add two new REST endpoints under `/v1/admin/` that expose the same operations.
- Rewrite the two CLIs to be thin HTTP clients that call those endpoints.
- Document all admin endpoints + CLI invocations in `docs/management-console.md`.

**Non-Goals:**
- Streaming/progress output for long-running jobs (out of scope for this iteration).
- Authentication / authorization on admin endpoints.
- Changing the REST server startup or the DuckDB connection management.
- Adding new CLI entry points beyond what already exists.

## Decisions

### Decision 1 — CLIs become HTTP clients; server retains all DB logic

**Chosen**: CLIs call `http://<MARKET_DATA_URL>/v1/admin/<operation>` via `httpx`
(already a project dependency) and print the JSON response to stdout.

**Alternative considered**: Share a DB abstraction layer so CLIs can detect whether the
server is running and switch modes.  Rejected — two code paths introduce drift and the
detection heuristic is fragile.

**Why `httpx` over `requests`**: `httpx` is already in the project's dependency tree
(used by tests).  No new dependency needed.

### Decision 2 — Base URL from environment variable `MARKET_DATA_URL`

**Chosen**: CLIs read `os.getenv("MARKET_DATA_URL", "http://localhost:8010")`.  Default
matches the development default so existing workflows need no change.

**Alternative**: Hardcode `localhost:8010`.  Rejected — would break staging/production
deployments.

### Decision 3 — New endpoints live in `admin.py`, not a new router

**Chosen**: Append to the existing `/v1/admin` router, which already has
`/import-ohlcv-cache` and `/migrate-fundamentals`.  Admin operations belong together.

### Decision 4 — Endpoint for compute-indicators accepts `symbol: str | None`

For a single-symbol call, the payload is `{"strategy": "best_sma", "symbol": "BTC"}`.
For bulk, omit `symbol`.  This mirrors the CLI's `--symbol` flag exactly.  The endpoint
iterates internally just as the CLI did, collecting per-instrument results.

Response body:
```json
{
  "ok": 3,
  "errors": 1,
  "results": [
    {"ticker": "BTC", "status": "ok", "elapsed_s": 0.42},
    {"ticker": "ETH", "status": "error", "error": "Insufficient OHLCV data"}
  ]
}
```

### Decision 5 — Endpoint for import-cmc-static uses server-side directory only

The server process has access to the filesystem; the client CLI does not need to send
files.  The endpoint accepts an optional `dir` field that overrides `CMC_STATIC_DIR` on
the server, matching the existing CLI's `dir` positional argument behaviour.

Response body: the existing `dict[str, int]` counts returned by `run_import()`.

### Decision 6 — CLI exit codes preserved

`compute-indicators` exits 1 on any per-instrument error (same as before).
`market-data import-cmc-static` exits 0 on success, 1 if the server returns an error.

## Risks / Trade-offs

- **Long-running bulk jobs block the HTTP event loop** — FastAPI runs synchronous DB
  code in a thread pool via `run_in_executor` implicitly for plain `def` routes, but
  `compute-indicators` for hundreds of instruments can run for minutes.  Mitigation:
  mark the new admin route handlers as plain `def` (not `async def`) so FastAPI
  dispatches them to the thread pool, keeping the event loop responsive.

- **No progress feedback during bulk run** — the CLI blocks until the full HTTP response
  returns.  Acceptable for now; the existing CLI had the same limitation via stdout
  line-by-line.  A future streaming/SSE endpoint can address this.

- **CLI fails if server is not running** — this is the intended behaviour; the error
  message from `httpx` (`Connection refused`) is clear enough for operators.

## Migration Plan

1. Add two route handlers to `src/market_data/api/rest/admin.py`.
2. Rewrite `src/market_data/cli/compute_indicators.py` to HTTP client.
3. Rewrite the `import-cmc-static` sub-command in `src/market_data/cli/__init__.py`.
4. Update tests in `tests/test_cli_compute_indicators.py`.
5. Add documentation section to `docs/management-console.md`.
6. No DB schema changes; no migrations needed.
7. Rollback: revert CLI files — server-side endpoints are additive and harmless.
