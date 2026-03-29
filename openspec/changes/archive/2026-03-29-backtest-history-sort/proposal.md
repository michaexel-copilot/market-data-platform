## Why

The precalculated backtests table has no heading and its columns are not sortable, making it hard to compare runs or find the best-performing strategy at a glance.

## What Changes

- Add a visible heading (e.g. "Cached Backtests") above the table
- Make all data columns in the backtest history table sortable (click header to sort ascending/descending, no external library dependency)

## Capabilities

### New Capabilities
- `backtest-history-sort`: Client-side sortable columns and heading for the precalculated backtests history table

### Modified Capabilities
<!-- none -->

## Impact

- `templates/backtest_history.html`: heading + sortable `<th>` click handlers
- Pure front-end change; no server-side or API changes required
