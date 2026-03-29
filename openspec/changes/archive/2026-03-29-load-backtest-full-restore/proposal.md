## Why

When a user clicks "Load" on a history row, only the original search-range parameters are restored into the form — the best period found is not set, the Best Parameters summary is not shown, and the validation trades table does not appear. The user must re-run the backtest to see the results they already computed, which is slow and confusing.

## What Changes

- The Load button in `backtest_history.html` will additionally carry `data-best-ind1-period`, `data-best-ind2-period`, and `data-filename` attributes
- `loadBacktestParams()` will set `ind1-min` and `ind1-max` both to the best ind1 period, and `ind2-min`/`ind2-max` both to the best ind2 period
- A new endpoint `GET /asset/{symbol}/backtest-cache/file/{filename}/results` will render the cached backtest result as full `backtest_results.html` HTML without re-running the optimization
- After loading params, the Load button's JS will trigger an HTMX GET to the new endpoint, populating `#backtest-results`

## Capabilities

### New Capabilities
- `load-backtest-restore-results`: Server endpoint that serves the full backtest results HTML (Best Parameters Found card + trade stats + validation trades table) for a previously cached run, identified by filename.

### Modified Capabilities
- `backtest-history-table`: The Load button behaviour changes — indicator range inputs are set to min=max=best period (instead of the original search range), and the results panel is populated immediately without re-running.

## Impact

- `templates/backtest_history.html`: add data attributes to Load button; update `loadBacktestParams()` JS
- `web.py`: add `GET /asset/{symbol}/backtest-cache/file/{filename}/results` endpoint
- No schema / data changes; reads existing cache files
