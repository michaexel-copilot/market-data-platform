## 1. draw_chart.py — prepare_chart_data

- [x] 1.1 Add `sma_high_period: int = 7` parameter to `prepare_chart_data()`; update the SMA High computation to use `sma_high_period` instead of `sma_period`
- [x] 1.2 Change the default value of `sma_period` in `prepare_chart_data()` from 44 to 7

## 2. draw_chart.py — backtest_strategy excursion tracking

- [x] 2.1 During each open position in `backtest_strategy()`, track the best and worst unrealised P&L seen on every candle (using daily close) from entry through exit
- [x] 2.2 On trade close, store `max_adverse_pnl` (worst unrealised) and `max_favourable_pnl` (best unrealised) in the trade dict; set both to `None` for open trades

## 3. draw_chart.py — draw_chart default and signature

- [x] 3.1 Update `draw_chart()` to accept and pass through `sma_high_period: int = 7` to `prepare_chart_data()`

## 4. web.py — route parameter and wiring

- [x] 4.1 Add `sma_high: int = 7` query parameter to the `asset_detail` route
- [x] 4.2 Change default value of the `sma` parameter from 44 to 7 in the route signature
- [x] 4.3 Pass `sma_high_period=sma_high` to `prepare_chart_data()` and forward `sma_high` / `sma_high_period` to the template context

## 5. web.py — chart cache helpers

- [x] 5.1 Update `_get_or_create_chart()` and `_get_or_create_highlighted_chart()` to accept and use `sma_high_period`

## 6. templates/asset_detail.html — SMA LOW spinner

- [x] 6.1 Rename the "SMA period" label to "SMA period LOW"
- [x] 6.2 Change the default/initial value reference in the spinner to use the new default (value comes from `sma_period` template variable — no change needed to template, only default wired via web.py; verify the spinner renders 7)
- [x] 6.3 Update the `keydown` handler: change the `Shift` branch step from `5` to `7`

## 7. templates/asset_detail.html — SMA HIGH spinner

- [x] 7.1 Add a "SMA period HIGH" spinner with id `sma-high-input`, name `sma_high`, default value `{{ sma_high }}`, range 1–500, styled identically to the LOW spinner
- [x] 7.2 Wire HTMX on the HIGH spinner: `hx-include="#pos-input, #tab-input, #sma-high-input"` on the LOW spinner and `hx-include="#pos-input, #tab-input, #sma-input"` on the HIGH spinner (mutual inclusion)
- [x] 7.3 Add the `keydown` keyboard handler for the HIGH spinner (same logic: ±1, Shift ±7, Ctrl+Shift ±10)
- [x] 7.4 Add hidden `<input id="sma-high-input" name="sma_high">` on Performance, Fundamentals, and Order tabs so `sma_high` survives tab switching

## 8. templates/asset_detail.html — Max Δ P&L column

- [x] 8.1 Add `<th>Max Δ P&L</th>` column header to the trades table
- [x] 8.2 Add the table cell for each trade row: show `max_adverse_pnl` (red) for profit trades, `max_favourable_pnl` (green) for loss trades, `—` for open trades
- [x] 8.3 Extend the `colspan` on the Total P&L tfoot row to account for the new column
