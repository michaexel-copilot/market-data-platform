## Why

The backtest results panel is cluttered and lacks usability: the validation trades table is always fully expanded (overwhelming for many rows), each history row has no quick way to delete stale runs, and the "Clear Cache" button deletes everything at once which is too destructive.

## What Changes

- Wrap the validation trades table in a collapsible Bootstrap accordion so it is hidden by default and can be expanded on demand
- Add a per-row "Delete" button to the precalculated backtests history table that removes only that specific cached result
- Remove the "Clear Cache" button from the backtest results panel

## Capabilities

### New Capabilities

- `val-trades-collapsible`: Validation trades table wrapped in a collapse toggle within `backtest_results.html`
- `backtest-history-delete`: Per-row delete button in the history table (`backtest_history.html`) that calls a DELETE endpoint for that specific cache file

### Modified Capabilities

- `backtest-cache`: New `delete_cache_by_file` helper (or reuse path-based delete) to remove a single cache entry by its filename, callable from the history table row

## Impact

- `templates/backtest_results.html`: wrap trades section in Bootstrap collapse
- `templates/backtest_history.html`: add Delete button column
- `web.py`: new `DELETE /asset/{symbol}/backtest-cache/{filename}` endpoint
- `backtest_engine.py`: expose a way to delete a cache entry by its exact file path/name
