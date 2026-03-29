## Context

`cache/backtest/` already stores all completed backtest results as JSON files named `{SYMBOL}_{ind1_type}_{ind2_type}_{exposure}_{hash}.json`. Each file contains the full result dict including `best_params`, `train_stats`, `val_stats`, and `open_position`. However, the parameters used to produce a result (date range, min/max ranges) are currently only in the SHA1 hash — they are not stored inside the JSON. This means we must also persist parameters alongside results to reconstruct the table row.

## Goals / Non-Goals

**Goals:**
- Show all cached backtest results for the current symbol in a table below `#run-backtest-btn`
- Include all input parameters (train start, train end, val start, ind1 type, ind2 type, exposure) and output metrics (train net P&L, val net P&L, val trade count)
- Table auto-refreshes after a new backtest run
- Each row has a "Load" button that fills the form fields without re-running
- Parameters stored inside the cache JSON so they are recoverable without parsing the filename

**Non-Goals:**
- Cross-symbol history comparison
- Sorting/filtering of history table (simple list is sufficient)
- Pagination (number of cached runs per symbol is expected to be small, <50)

## Decisions

### D1: Store input parameters inside cache JSON

When `save_cache()` writes a result, also embed the input parameters (`ind1_type`, `ind2_type`, `ind1_min`, `ind1_max`, `ind2_min`, `ind2_max`, `exposure`, `train_start`, `train_end`, `val_start`) under a `_params` key in the JSON.

**Rationale**: The SHA1 hash filename cannot be decoded back to parameters. Embedding them in the JSON is the simplest approach and keeps each file self-contained.

**Alternative considered**: Store a separate index file. Rejected — adds complexity and sync risk.

### D2: `list_cache(symbol)` scans the cache directory by filename prefix

`list_cache(symbol)` globs `cache/backtest/{SYMBOL.upper()}_*.json`, loads each, and returns a list of dicts. Files without a `_params` key (legacy) are skipped without error.

### D3: New endpoint `GET /asset/{symbol}/backtest-history` returns rendered HTML

Returns a `backtest_history.html` partial. The endpoint is lightweight — just scans and renders.

### D4: HTMX loads history on accordion open + refreshes after POST /backtest

In `asset_detail.html`, add `hx-get="/asset/{symbol}/backtest-history"` on the accordion section with `hx-trigger="intersect once"` for initial load, and use `hx-on::after-request` on the Run Backtest button to re-trigger the history load after a successful backtest.

### D5: "Load" button uses HTMX `hx-on:click` to populate form fields via JS

A small inline `onclick` handler reads `data-*` attributes from the row and sets input values. No new endpoint needed.

## Risks / Trade-offs

- **Legacy cache files without `_params`**: Silently skipped. Users need to re-run to see them in history. → Acceptable; old cached results will appear after next run.
- **Race condition on concurrent runs**: Not an issue — single-user tool, sequential writes.
