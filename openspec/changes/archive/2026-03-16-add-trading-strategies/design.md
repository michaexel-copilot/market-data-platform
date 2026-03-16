## Context

`FindShortOpportunites/web.py` currently runs a brute-force SMA grid search inline on every HTTP request. The computation takes several seconds per instrument, blocks the web process, and is not reusable. The backtest engine (`sma`, `backtest_short_strategy`, `backtest_long_strategy`) lives in `draw_chart.py`, a UI-oriented module with chart-rendering dependencies not suitable for import by a separate service.

`market-data-platform` already owns the canonical OHLCV store (DuckDB), the instrument registry, and the REST API surface. Moving strategy computation here co-locates it with its primary data dependency and provides a clean precompute-then-query pattern for any future consumer.

## Goals / Non-Goals

**Goals:**
- Persist precomputed indicator values in DuckDB, keyed by instrument + strategy + indicator + parameters.
- Provide a REST read endpoint so `FindShortOpportunites` (and future clients) can retrieve stored values.
- Provide a CLI command to bulk-compute indicators for all active instruments with OHLCV data.
- Keep the backtest engine as pure Python functions with no I/O — usable by both the CLI and the REST compute endpoint.
- Provide a REST compute endpoint (POST) as the foundation for a future UI-triggered compute flow.

**Non-Goals:**
- Real-time / streaming indicator computation.
- Indicator computation for intervals other than `1d`.
- Exposing raw backtest trade-by-trade results through the new API (that remains in `FindShortOpportunites`).
- Migrating the chart rendering or other UI logic out of `FindShortOpportunites`.
- Automatic scheduling / cron setup (operator concern).

## Decisions

### D1: Backtest engine location — `market_data/strategies/backtest.py`

The three functions (`sma`, `backtest_short_strategy`, `backtest_long_strategy`) are copied verbatim from `FindShortOpportunites/draw_chart.py` into a new module `market_data/strategies/backtest.py`. They have zero I/O and no chart dependencies. This is a clean copy, not a shared library import, because the two projects have separate virtual environments and release cycles. The source of truth for these functions moves to `market-data-platform`; `FindShortOpportunites` will eventually import them via HTTP (already the case after this change for the best-SMA result).

*Alternative considered*: extract a shared `trading-engine` PyPI-style package. Rejected — premature abstraction for two modules on the same filesystem; the overhead of a third package outweighs the benefit at this scale.

### D2: Strategy dispatch — explicit registry, not plugin system

A `STRATEGY_REGISTRY` dict maps string names to callable strategy functions:

```python
STRATEGY_REGISTRY: dict[str, Callable] = {
    "best_sma": compute_best_sma,
}
```

New indicators are added by registering a new callable. No dynamic import magic.

*Alternative considered*: entry-point-based plugin discovery. Rejected — premature for a small internal codebase.

### D3: Table schema — (instrument_id, strategy_name, indicator_name) primary key, parameters in JSON column

```sql
CREATE TABLE trading_strategies (
    instrument_id   VARCHAR      NOT NULL,
    strategy_name   VARCHAR      NOT NULL,
    indicator_name  VARCHAR      NOT NULL,
    indicator_value DOUBLE       NOT NULL,
    parameters      JSON,
    computed_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, strategy_name, indicator_name)
);
```

The composite PK ensures one value per (instrument, strategy, indicator) — the last-computed wins. Parameters are stored for auditability but are **not** part of the key. This is intentional: the CLI uses fixed defaults, so there is one canonical value per indicator. If future workflows need parameter-sensitive caching, a compound key including a parameter hash can be added in a new migration.

*Alternative considered*: include parameters in the PK. Rejected — introduces stale-data risk (multiple rows per instrument, unclear which to serve) and complicates the read endpoint without clear benefit given the current single-parameter-set use case.

### D4: CLI reads OHLCV from DuckDB, not filesystem cache

The CLI calls `market_data.db.connection.get_connection()` and queries the `ohlcv` table directly — the same data source already used by the REST OHLCV endpoint. This removes the dependency on `FindShortOpportunites`' file-based cache and makes the CLI self-contained within `market-data-platform`.

### D5: `FindShortOpportunites` calls the new GET endpoint; compute stays server-side

After this change `FindShortOpportunites/web.py` replaces the inline `_find_best_sma` call with an `httpx` GET to `market-data-platform`. It does **not** call the POST compute endpoint — that would just reintroduce the latency problem with an extra hop. The expectation is: run `compute-indicators` CLI first, then the UI reads cached values. The UI shows a clear error if no precomputed value exists.

## Risks / Trade-offs

- **Staleness** — Precomputed values age as new OHLCV arrives. Mitigation: the `computed_at` column is returned in the API response, and the CLI can be re-run on a schedule.
- **OHLCV data absent** — If an instrument exists in the `instruments` table but has no OHLCV rows, the CLI and compute endpoint must fail that instrument explicitly (logged as error, not silently skipped). Mitigation: enforced by spec and implementation.
- **Parameter mismatch** — A user running the UI with non-default `sl_short`/`sl_long` values will receive a best-SMA value that was computed with different parameters. Mitigation: the GET response includes `parameters`, the UI should show a note that the computed parameters may differ. Full parameter-aware caching is deferred.
- **Copy-paste maintenance** — Backtest functions are duplicated between `draw_chart.py` (legacy) and `market_data/strategies/backtest.py` (new). Mitigation: `FindShortOpportunites` still imports them from `draw_chart.py` for chart rendering only; the strategic direction is that `market-data-platform` owns the functions going forward.

## Migration Plan

1. Run `uv run migrate` in `market-data-platform` to apply `017_trading_strategies.sql`.
2. Run `uv run compute-indicators --strategy best_sma` to populate initial values.
3. Configure `MARKET_DATA_PLATFORM_URL` environment variable in `FindShortOpportunites` (default: `http://localhost:8010`).
4. Deploy updated `FindShortOpportunites`; the `GET /asset/{symbol}/best-sma` endpoint will now proxy to `market-data-platform`.

**Rollback**: revert `FindShortOpportunites/web.py` to the inline `_find_best_sma` call. The `trading_strategies` table can remain in place — it has no effect on existing functionality.

## Open Questions

- *(none — all decisions above are resolved for this scope)*
