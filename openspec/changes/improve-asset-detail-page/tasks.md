## 1. Asset Detail Layout Updates

- [x] 1.1 Remove the `Chart & Trades: Chart` accordion item from the asset detail page UI.
- [x] 1.2 Reorder the asset detail analysis sections so Validation Trades renders directly below the Cached Backtests table.
- [x] 1.3 Ensure the updated section order is applied consistently for both initial render and post-load rerender states.

## 2. Cached Backtest Load Flow

- [x] 2.1 Add a shared post-load handler used by both cached-backtest load paths (Load button and new run completion path).
- [x] 2.2 In the shared post-load handler, automatically open the `Performance` accordion item after successful cached backtest load.
- [x] 2.3 Guard the post-load flow so accordion-open and chart-render actions occur only after backtest payload/state is committed.

## 3. Performance Chart Behavior

- [x] 3.1 Render a 1-day granularity chart in `Performance` that overlays price and indicators for the loaded backtest context.
- [x] 3.2 Implement chart-window selection: use `opened_trade_ts - 5 days` to today when trade context exists.
- [x] 3.3 Implement fallback chart-window selection: show at least the last 30 days through today when trade context is unavailable.
- [x] 3.4 Normalize and align price/indicator series on a shared daily date index before plotting.
- [x] 3.5 Add graceful fallback rendering (e.g., price-only or explanatory state) when indicator series are missing.

## 4. Validation and Regression Coverage

- [x] 4.1 Add/update UI tests to verify the chart accordion item is removed and Validation Trades appears directly below Cached Backtests.
- [x] 4.2 Add/update tests to verify `Performance` auto-opens on both cached-backtest load entry points.
- [x] 4.3 Add/update tests for chart-window logic (trade-context mode vs 30-day fallback mode).
- [x] 4.4 Run relevant frontend/integration test suites and fix regressions introduced by layout and interaction changes.
