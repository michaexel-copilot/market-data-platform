## Why

The Chart & Trades tab's trade table lacks context about price excursions during each trade's holding period, and the single shared SMA period makes it impossible to tune the signal line (SMA Low) independently from the SMA High reference line. These additions improve risk assessment and strategy refinement without changing the core short-selling logic.

## What Changes

- **Trade table — new "Max Δ P&L" column**: For each closed trade, compute and display the worst-case unrealised P&L that occurred during the holding period. For a winning trade this is the maximum adverse excursion (highest price seen, i.e. closest to stop-loss); for a losing trade this is the maximum favourable excursion (lowest price seen, i.e. best unrealised profit). Shown in USD with the same sign convention as the P&L column.
- **SMA period spinner — renamed and retuned**: Label changes from "SMA period" to "SMA period LOW". Default value changes from 44 to 7. The `Shift + "+/-"` shortcut increments by 7 instead of 5.
- **New "SMA period HIGH" spinner**: Independent lookback window for the SMA High line. Default value 7. Same keyboard shortcuts as SMA period LOW (`+/-` = ±1, `Shift+"+/-"` = ±7, `Ctrl+Shift+"+/-"` = ±10). The spinner's value is passed as a new `sma_high` URL parameter and stored as a hidden input on non-chart tabs.

## Capabilities

### New Capabilities

- `trade-table-delta-column`: Computes maximum adverse/favourable excursion for each trade inside `backtest_strategy()` and displays it as a new column in the trades table in `asset_detail.html`.
- `dual-sma-period-spinners`: Introduces a second, independent SMA period for the High line. Affects spinner UI in `asset_detail.html`, URL parameter in `web.py`, `prepare_chart_data()` signature in `draw_chart.py`, and keyboard-shortcut defaults for the renamed LOW spinner.

### Modified Capabilities

*(none — no existing spec-level requirements are changing)*

## Impact

- **`draw_chart.py`**: `prepare_chart_data()` gains a `sma_high_period` parameter (default 7). `backtest_strategy()` gains per-trade `max_adverse_pnl` / `max_favourable_pnl` fields computed by tracking the daily high/low during each open position.
- **`web.py`**: `asset_detail` route gains a `sma_high: int = 7` query parameter; both `sma` and `sma_high` are threaded through to `prepare_chart_data()` and forwarded to the template.
- **`templates/asset_detail.html`**: SMA period spinner label updated; `Shift` step changed to 7; new SMA HIGH spinner added with its own `hx-include` wiring; hidden `sma-high-input` added on Performance/Fundamentals/Order tabs so it survives tab switching; trades table gains a "Max Δ P&L" column header and cell.
- **`USER_MANUAL.md`**: Keyboard reference table and trade table column descriptions updated.
- No breaking changes to existing URL parameters (`sma` is unchanged); `sma_high` is additive with a default value.
