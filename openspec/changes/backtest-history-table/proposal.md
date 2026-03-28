## Why

After running one or more backtests for an asset, the user has no way to compare results across different parameter combinations. All previous runs are stored in `cache/backtest/` as JSON files but are invisible in the UI. A history table directly below the "Run Backtest" button would let users see all cached runs at a glance and quickly identify the best-performing configuration.

## What Changes

- **ADD** a `GET /asset/{symbol}/backtest-history` endpoint that reads all cached backtest JSON files for the given symbol and returns a structured list of runs (parameters + P&L summary).
- **ADD** a history table section rendered below `#run-backtest-btn` in `asset_detail.html`, loaded via HTMX on accordion open and refreshed after each new backtest run. Columns: Train Start, Train End, Val Start, Ind 1, Ind 2, Exposure, Train Net P&L, Val Net P&L, Trades (val).
- **ADD** a small "Load" button per row that repopulates the backtest form with that row's parameters (without re-running).

## Capabilities

### New Capabilities

- `backtest-history-table`: Read all cached backtest results for an asset, display them in a sortable summary table below the "Run Backtest" button with columns for all parameters and P&L figures.

### Modified Capabilities

- `backtest-cache`: Add a `list_cache(symbol)` function to `backtest_engine.py` that scans `cache/backtest/` for all JSON files belonging to a symbol and returns their decoded contents alongside the original parameters (decoded from the filename/data).

## Impact

- **`backtest_engine.py`**: New `list_cache(symbol)` helper.
- **`web.py`**: New `GET /asset/{symbol}/backtest-history` endpoint returning rendered HTML.
- **`templates/asset_detail.html`**: HTMX trigger to load `#backtest-history` div on accordion expand, refresh after POST `/backtest`.
- **`templates/backtest_history.html`**: New partial template for the history table.
- No new dependencies.
