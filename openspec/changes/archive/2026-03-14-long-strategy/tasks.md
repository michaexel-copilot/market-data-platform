## 1. draw_chart.py — Short Strategy Refactor

- [x] 1.1 Rename `backtest_strategy` to `backtest_short_strategy` and add `stop_loss_pct: float = 0.10` parameter
- [x] 1.2 Replace hardwired `entry_price * 1.10` stop with `entry_price * (1 + stop_loss_pct)` in `backtest_short_strategy`

## 2. draw_chart.py — Long Strategy Backtest

- [x] 2.1 Add `backtest_long_strategy(candles, sma_high, position_size_usd, stop_loss_pct)` with entry on close crossing above SMA High
- [x] 2.2 Implement long stop loss: exit at `entry_price * (1 - stop_loss_pct)` when close falls to or below that level
- [x] 2.3 Implement long take profit: exit at `sma_high[i]` when `sma_high[i] > entry_price` and `close[i] >= sma_high[i]`
- [x] 2.4 Implement long P&L: `(exit_price - entry_price) / entry_price * position_size_usd`
- [x] 2.5 Add excursion tracking (`max_adverse_pnl`, `max_favourable_pnl`) to `backtest_long_strategy`

## 3. draw_chart.py — Chart Updates

- [x] 3.1 Replace `highlight` param with `hl_short` and `hl_long` in `draw_chart()`; update crosshair rendering (blue/orange for short, green/red for long)
- [x] 3.2 Add `sl_short: float = 0.10` and `sl_long: float = 0.10` params to `draw_chart()`; pass to respective backtest functions
- [x] 3.3 Update chart filename pattern to include both highlight indices and both SL values

## 4. web.py — Route and Cache Helpers

- [x] 4.1 Add URL params `sl_short: int = 10`, `sl_long: int = 10`, `hl_long: int | None = None`, `strategy_tab: str = "short"` to `asset_detail` route
- [x] 4.2 Update `backtest_short_strategy` call: pass `stop_loss_pct=sl_short/100.0`
- [x] 4.3 Call `backtest_long_strategy` with `sma_high`, `position_size_usd`, `stop_loss_pct=sl_long/100.0`; format long trades for template
- [x] 4.4 Update `_today_prefix`, `_find_existing_chart`, `_get_or_create_chart`, `_get_or_create_highlighted_chart` to include `sl_short`, `sl_long`, `hl_short` (rename from `highlight`), `hl_long` in filenames and signatures
- [x] 4.5 Pass `long_trades`, `sl_short`, `sl_long`, `hl_long`, `strategy_tab` to template context

## 5. templates/asset_detail.html — Spinners

- [x] 5.1 Add "SL Short %" spinner (id=`sl-short-input`, name=`sl_short`, default 10, min 1, max 50) with same keyboard handler as SMA spinners
- [x] 5.2 Add "SL Long %" spinner (id=`sl-long-input`, name=`sl_long`, default 10, min 1, max 50) with same keyboard handler

## 6. templates/asset_detail.html — Sub-tabs

- [x] 6.1 Add Short / Long pill sub-tab nav below the chart and above the trades content
- [x] 6.2 Add hidden `<input id="strategy-tab-input" name="strategy_tab">` carrying the active tab value
- [x] 6.3 Add hidden `<input id="hl-long-input" name="hl_long">` carrying the long highlight index
- [x] 6.4 Include `#sl-short-input, #sl-long-input, #strategy-tab-input, #hl-long-input` in hx-include of SMA LOW spinner
- [x] 6.5 Include same new ids in hx-include of SMA HIGH, Position Size, and sub-tab pill buttons

## 7. templates/asset_detail.html — Long Trades Table

- [x] 7.1 Render long trades summary bar (count, total P&L, avg P&L/trade) above long table when `strategy_tab == "long"`
- [x] 7.2 Render long trades table with columns: #, Entry Date, Entry $, Exit Date, Exit $, P&L, Max Δ P&L
- [x] 7.3 Implement Max Δ P&L cell logic for long trades (mirrored: adverse=price fell, favourable=price rose)
- [x] 7.4 Wire long trade row clicks: `hx-vals` sets `hl_long=<index>`, includes all existing + new hidden inputs

## 8. templates/asset_detail.html — Hidden Inputs on Non-Chart Tabs

- [x] 8.1 Add hidden `sl-short-input`, `sl-long-input`, `strategy-tab-input`, `hl-long-input` on Performance tab (alongside existing `sma-high-input`)
- [x] 8.2 Add same hidden inputs on Fundamentals tab
- [x] 8.3 Add same hidden inputs on Order tab
- [x] 8.4 Update short trade row hx-include to also carry `#sl-short-input, #sl-long-input, #strategy-tab-input, #hl-long-input`
