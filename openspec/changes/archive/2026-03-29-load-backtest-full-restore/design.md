## Context

When a user clicks "Load" on a history row, `loadBacktestParams()` populates the backtest form with the original search-range parameters but does nothing else. The `#backtest-results` div remains empty — the user must hit "Run Backtest" again, which re-hits the cache anyway, to see the results they already have. This causes unnecessary friction.

The codebase already has `backtest_results.html` which renders the full results panel (Best Parameters Found card, train/val stats, validation trades table). The existing cache files contain all necessary data (`best_params`, `train_stats`, `val_stats`, `val_trades`, `open_position`, `_params`).

## Goals / Non-Goals

**Goals:**
- When "Load" is clicked, set indicator period spinners to min=max=best period found
- Immediately populate `#backtest-results` with the cached results (no re-run)
- Reuse the existing `backtest_results.html` template

**Non-Goals:**
- Changing how backtest caching or optimization works
- Adding a new persistence layer
- Modifying the Run Backtest POST flow

## Decisions

### Decision: New GET endpoint for cached results by filename

**Chosen:** `GET /asset/{symbol}/backtest-cache/file/{filename}/results`

Loads the JSON cache file from `cache/backtest/{filename}`, extracts `_params` and result data, renders `backtest_results.html`.

**Alternative considered:** Trigger the existing POST with min=max=best params  
**Rejected because:** The POST is keyed by a hash of all params including the search range. A load with min=max=best would compute a different hash and miss the cache, triggering a full re-run.

### Decision: Pass best periods as data attributes on the Load button

The Load button in `backtest_history.html` already carries `data-*` attributes from `_params`. We add `data-best-ind1-period` and `data-best-ind2-period` from `best_params`, and `data-filename` from `r._filename`.

The `loadBacktestParams()` JS then: (1) sets min/max inputs to best period, (2) calls `htmx.ajax('GET', '/asset/SYMBOL/backtest-cache/file/FILENAME/results', {target:'#backtest-results', swap:'innerHTML'})`.

The `symbol` is already available to the template as `{{ symbol }}`, so it can be injected as a `data-symbol` attribute on the button, or the endpoint URL can be pre-built per row.

### Decision: Pre-build the results URL per row in the template

Rather than reconstructing the URL in JS from separate pieces, embed the full URL as `data-results-url="/asset/{{ symbol }}/backtest-cache/file/{{ r._filename }}/results"` on the Load button. This keeps JS simple and avoids URL-construction bugs.

## Risks / Trade-offs

- **Risk:** Cache file deleted between history render and Load click → 404 from new endpoint  
  **Mitigation:** Return a friendly error HTML partial (reuse the existing alert pattern) rather than a server error

- **Trade-off:** Adding `data-filename` and `_filename` field — cache entries returned by `list_cache()` must include the filename. `list_cache()` currently returns the parsed dict; it needs to inject `_filename` into each dict.

## Migration Plan

No data migrations needed. All changes are additive (new endpoint, template data attribute additions, JS update). Fully backward compatible — existing cache files do not need modification.
