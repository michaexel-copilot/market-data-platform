## Why

Finding the optimal SMA pair for a given asset currently requires manual trial-and-error with the two spinners, which is slow and misses non-obvious combinations. An automated brute-force search with cached results lets traders instantly jump to the best-performing SMA configuration for both short and long strategies.

## What Changes

- Add a **"Find Best SMA"** button on the Chart & Trades tab that triggers a brute-force search over a configurable SMA range, scores each pair by average P&L per trade (short + long combined), and updates the SMA LOW and SMA HIGH spinners to the winning values.
- Cache the search result per (symbol, date) so repeated clicks are instant.
- **Unified trade table**: merge the two separate short/long trade tables into one combined table with a "Direction" column; colorize all row columns **except** P&L and Max-Delta-P&L with a light red background for short trades and a light green background for long trades.
- **Dual strategy summary**: show a compact summary row / card for both short and long strategies (trade count, win rate, total P&L, avg P&L per trade) above the unified table.
- **SMA spinner side-by-side layout**: place the SMA period LOW and SMA period HIGH spinners in one row, each with its corresponding stop-loss % field and direction label directly beneath it.

## Capabilities

### New Capabilities
- `find-best-sma-optimization`: Brute-force search over SMA LOW × SMA HIGH grid, scoring by average profit per trade (both strategies combined); result is cached to disk per (symbol, date); HTMX endpoint updates both spinners on completion.

### Modified Capabilities
- `dual-sma-period-spinners`: Layout changes — spinners placed side-by-side with corresponding SL % fields and direction labels; values still controlled by `sma-input` / `sma-high-input` hidden fields.
- `long-strategy-backtest`: Short and long trade tables are merged into a single unified table; summaries for both strategies are displayed above the table; short rows are highlighted light-red, long rows light-green (excluding P&L and Max-Delta-P&L columns).

## Impact

- **`web.py`**: new HTMX route `/asset/{symbol}/best-sma` for the optimization search; caching logic added; response updates both spinner inputs via `hx-swap-oob` or a partial re-render.
- **`draw_chart.py`** / **`draw_chart`** module: `backtest_short_strategy` and `backtest_long_strategy` called in a nested loop over SMA ranges — no API changes, just new usage.
- **`templates/asset_detail.html`**: "Find Best SMA" button added near the spinners; spinner layout refactored to side-by-side; short + long trade tables merged into one; summary section added above the table.
- **Cache**: a new cache sub-folder (e.g. `cache/best_sma/`) or an in-memory dict keyed by `(symbol, date)` stores search results.
- No new Python dependencies required.
