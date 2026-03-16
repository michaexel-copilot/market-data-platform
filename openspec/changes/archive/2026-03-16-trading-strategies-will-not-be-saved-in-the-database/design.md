## Context

`ohlcv` is empty because `import-ohlcv-cache` has never been called as a bulk operation. 144 hourly JSON files exist at `/appdata/eodhd/intraday_historical_data/1-hour/<TICKER>.json` (each named by ticker), covering ~5.5 years of data. The `compute_best_sma` strategy queries `interval='1d'` which doesn't exist — only `1h` rows will be present after import. `FindShortOpportunites/web.py` has a two-level local cache (in-memory + per-day JSON files) for best_sma results that bypasses the database entirely.

## Goals / Non-Goals

**Goals:**
- Provide a `uv run import-ohlcv` CLI that bulk-imports hourly OHLCV from the eodhd cache into the database for all active instruments (or a single one).
- Make `compute_best_sma` work against the `1h` data by aggregating to daily inside the strategy SQL.
- Remove the local file cache from `web.py`; the market-data-platform database is the single source of truth.

**Non-Goals:**
- Fetching OHLCV from the network/API during this change.
- Changing the backtest logic or SMA grid parameters.
- Modifying how `FindShortOpportunites/web.py` calls the REST API for anything other than removing the local cache.

## Decisions

### Decision: CLI delegates to REST endpoint (Option B — two explicit steps)
The `import-ohlcv` CLI POSTs to a new `POST /v1/admin/import-ohlcv` endpoint, mirroring the existing `compute-indicators` CLI/endpoint pattern. The endpoint handles the bulk loop server-side, returning `{ok, errors, results}`.

**Alternative considered**: Auto-import inside `compute-indicators`. Rejected — separation of concerns; import and compute are distinct operations with different cadences.

### Decision: Aggregate 1h → daily inside `compute_best_sma` using SQL
Replace the direct `WHERE interval='1d'` query with a CTE that groups `1h` rows by UTC date using `DATE_TRUNC('day', ts)`. Within each day: `open` = value at `MIN(ts)`, `high` = `MAX(high)`, `low` = `MIN(low)`, `close` = value at `MAX(ts)`, `volume` = `SUM(volume)`.

**Alternative considered**: Storing an aggregated `1d` copy in the `ohlcv` table. Rejected — adds ingestion complexity; on-the-fly aggregation in a CTE is straightforward in DuckDB and avoids data duplication.

### Decision: No fallback computation in `web.py`
Remove `_find_best_sma`, both cache helpers, and the in-memory dict. If the API returns 404, return HTTP 503 to the caller. The user must run `import-ohlcv` + `compute-indicators` first.

**Alternative considered**: Keep local fallback as a safety net. Rejected — it obscures whether the database pipeline is working, and the file cache produces stale results silently.

## Risks / Trade-offs

- [Risk] Instrument not in the `instruments` table → import silently skips it, `compute-indicators` still fails for that ticker. → Mitigation: per-ticker `error` status in the results payload; user can detect and fix separately.
- [Risk] `DATE_TRUNC` aggregation drops partial days at the boundaries. → Mitigation: acceptable; training uses 80% of candles, edge effects are negligible.
- [Risk] `web.py` returns 503 where it previously silently fell back. → Mitigation: this is intentional and expected — users must populate the DB first.

## Migration Plan

1. Deploy / restart market-data-platform (no schema migration required).
2. Run once: `uv run import-ohlcv --interval 1h`
3. Run once: `uv run compute-indicators --strategy best_sma`
4. `trading_strategies` is populated; `web.py` picks up values from the API.
