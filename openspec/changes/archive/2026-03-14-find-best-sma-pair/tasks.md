## 1. Backend — Best SMA Optimization Endpoint

- [x] 1.1 Add `BEST_SMA_CACHE: dict[tuple[str, date], tuple[int, int]]` module-level dict to `web.py`
- [x] 1.2 Add `find_best_sma(symbol: str, sl_short: float, sl_long: float, pos: float) -> tuple[int, int]` helper in `web.py` that iterates SMA LOW ∈ [3,50] × SMA HIGH ∈ [3,50], calls `prepare_chart_data`, `backtest_short_strategy`, `backtest_long_strategy`, scores each pair by combined avg closed-trade P&L, and returns the winning (sma_low, sma_high)
- [x] 1.3 Add `/asset/{symbol}/best-sma` GET route in `web.py` that checks `BEST_SMA_CACHE`, calls `find_best_sma` on miss, stores result in cache, and returns `JSONResponse({"sma": ..., "sma_high": ...})`

## 2. UI — Find Best SMA Button

- [x] 2.1 Add a "Find Best SMA" button in `asset_detail.html` (Chart & Trades tab, below the spinners row) that calls `/asset/{symbol}/best-sma` via `hx-get`, passes `sl_short`, `sl_long`, `pos`, `network` via `hx-include`, and uses `hx-on::after-request` (or a small inline script) to trigger a full `#detail-pane` reload with the returned `sma` and `sma_high` values
- [x] 2.2 Add a loading indicator on the button using HTMX `htmx-indicator` class or an `aria-busy` spinner icon while the request is in flight

## 3. UI — Side-by-Side Spinner Layout

- [x] 3.1 Refactor the spinner section in `asset_detail.html` to use a Bootstrap `row` / `col` layout: left column holds SMA period LOW spinner + SL Short % field (with "Short" direction label), right column holds SMA period HIGH spinner + SL Long % field (with "Long" direction label)

## 4. UI — Unified Trade Table

- [x] 4.1 In `asset_detail.html` (Chart & Trades tab), remove the `strategy_tab` toggle (Short / Long buttons)
- [x] 4.2 Merge the Short and Long trade table blocks into a single unified Jinja2 block that combines `trades` and `long_trades`, tagging each row with its direction, sorted by entry date descending
- [x] 4.3 Add a "Dir" column as the first data column (after "#") displaying "Short" or "Long"
- [x] 4.4 Apply inline `style="background-color:#ffe8e8"` to each short-direction cell for all columns except P&L (index 5) and Max-Delta-P&L (index 6); apply `style="background-color:#e8f5e8"` for long-direction cells in the same columns
- [x] 4.5 Update the `hx-vals` on each row to pass either `highlight` (short) or `hl_long` (long) appropriately, and update `hx-include` to omit `strategy-tab-input` (no longer needed)

## 5. UI — Dual Strategy Summary

- [x] 5.1 Add a dual strategy summary section above the unified table in `asset_detail.html`: short summary (closed trade count, total P&L, avg P&L) on the left, long summary on the right — both always rendered when trades exist

## 6. Backend — Remove strategy_tab dependency

- [x] 6.1 In `web.py` `asset_detail()`, remove the `strategy_tab` query parameter or keep it as a no-op (the template no longer uses it); ensure short and long trades lists are still both passed to the template context
