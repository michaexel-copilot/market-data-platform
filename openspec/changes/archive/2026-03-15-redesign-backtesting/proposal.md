## Why

The "Find Best SMA" optimisation currently uses all available candles, meaning the winning SMA pair is evaluated on the same data it was selected from — an in-sample bias that overstates real-world effectiveness. Splitting data 80/20 allows the selected SMA to be validated on unseen candles, giving the user an honest out-of-sample performance view.

## What Changes

- The SMA optimisation grid search (`_find_best_sma`) SHALL use only the **first 80 %** of candles (chronologically) to score SMA pairs.
- The existing in-process day cache for `_find_best_sma` SHALL be removed; the result is **always recalculated** because the logic change invalidates any cached value from prior runs.
- After "Find Best SMA" resolves, the **Chart & Trades** accordion SHALL run the full backtest on the **remaining 20 % of candles** (validation period) and display the results in a clearly labelled section inside the Trade Summary area.
- Both the **80 % training window** and the **20 % validation window** SHALL show their inclusive date ranges (e.g. "2020-01-01 → 2024-04-15" and "2024-04-16 → 2025-03-15") so the user can tell what data each section covers.
- The existing Trades table continues to show **all candles** (full history) with the optimised SMA applied — only the summary sections are split.

## Capabilities

### New Capabilities
- `out-of-sample-performance`: Compute and display the backtest summary (short + long trade counts, total P&L, avg P&L per trade) for the held-out validation window (last 20 % of candles) using the SMA returned by "Find Best SMA". Display this summary above or alongside the existing in-sample summary, with clearly labelled date-range headers.

### Modified Capabilities
- `find-best-sma-optimization`: Restrict the grid search to the first 80 % of available candles; remove the in-process day cache so results are always freshly computed.

## Impact

- `web.py` — `_find_best_sma`: remove `BEST_SMA_CACHE` lookup/store; slice candles to 80 % before the grid search.
- `web.py` — best-sma route handler: after finding the winning pair, run `backtest_short_strategy` + `backtest_long_strategy` on the last 20 % of (unscaled-then-scaled) candles and pass the results to the template.
- `templates/asset_detail.html`: add a new "Validation (out-of-sample)" summary block with date-range header, trade counts, total P&L, and avg P&L; label the existing summary as "Optimisation (in-sample)".
- No changes to `draw_chart.py`, `perf_data.py`, or external APIs.
