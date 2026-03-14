## Why

The app currently backtests only a short strategy. Adding a mirrored long strategy lets users evaluate both sides of the market on the same chart and compare outcomes head-to-head. The stop loss is also hardwired at 10%, which prevents realistic scenario testing; making it configurable per strategy is the natural companion change.

## What Changes

- **New long strategy backtest**: mirrors the short strategy using SMA High as the signal line — entry when close crosses above SMA High, stop when price falls 10% (configurable), take profit when SMA High rises above entry price and close falls back to it.
- **Configurable stop loss**: a separate stop-loss % spinner for each strategy (SL Short % and SL Long %), both defaulting to 10%. Replaces the hardwired `entry × 1.10` / `entry × 0.90` constants.
- **Strategy sub-tabs**: a Short / Long sub-tab nav inside the "Chart & Trades" tab, each with its own trades table, summary bar (count · Total P&L · Avg P&L), and Max Δ P&L excursion column.
- **Overlapping crosshairs**: short trade highlights (blue/orange) and long trade highlights (green/red) are independent — selecting a trade in one sub-tab does not clear the highlight from the other. Both can appear on the chart simultaneously.
- **Sub-tab state preserved on reload**: a hidden input carries the active sub-tab through all HTMX partial reloads triggered by spinner changes.

## Capabilities

### New Capabilities

- `long-strategy-backtest`: backtest engine for the long strategy — `backtest_long_strategy()` in `draw_chart.py`, mirrored signal/exit logic from the short strategy using SMA High, Max Δ P&L excursion tracking, green/red chart crosshairs independent of short crosshairs.
- `configurable-stop-loss`: per-strategy stop-loss % URL params (`sl_short`, `sl_long`), UI spinners with keyboard shortcuts, wired into both backtest functions; replaces the hardwired 1.10/0.90 constants.
- `strategy-sub-tabs`: Short / Long sub-tab nav within the Chart & Trades section, each rendering its own summary bar and trades table; active sub-tab preserved across HTMX reloads via hidden input.

### Modified Capabilities

- `dual-sma-period-spinners`: existing spinner hx-include chains must be extended to carry the new `sl_short`, `sl_long`, and `strategy_tab` hidden inputs.
- `trade-table-delta-column`: long trades table must also include the Max Δ P&L column with mirrored excursion semantics (adverse = price fell; favourable = price rose).

## Impact

- **`draw_chart.py`**: `backtest_strategy()` renamed `backtest_short_strategy()`, gains `stop_loss_pct` param; new `backtest_long_strategy()` added; `draw_chart()` gains `hl_long` param and `sl_short`/`sl_long` params; chart filename updated to include both highlight indices and both SL values.
- **`web.py`**: new URL params `sl_short: float = 0.10`, `sl_long: float = 0.10`, `hl_long: int | None`; calls both backtest functions; passes long trades and params to template; all cache helpers updated.
- **`templates/asset_detail.html`**: two new spinners (SL Short %, SL Long %); Short/Long sub-tab nav; second trades table + summary bar; hidden inputs for `sl_short`, `sl_long`, `strategy_tab`, `hl_long` threaded through all hx-include chains on all tabs.
