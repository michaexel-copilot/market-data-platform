## 1. Consolidate hidden inputs

- [x] 1.1 Move all `<input type="hidden">` state-carrier elements (sma, sma_high, sl_short, sl_long, pos, resolution, highlight, hl_long, strategy_tab, tab) to a single block at the top of the partial, removing the duplicate copies that existed in each tab branch.

## 2. Remove tab navigation

- [x] 2.1 Delete the four-button tab-group `<div class="btn-group mb-3" ...>` block from `asset_detail.html`.
- [x] 2.2 Remove the `<input type="hidden" id="tab-input">` element (tab routing is no longer needed).

## 3. Build accordion structure

- [x] 3.1 Wrap the entire content area in `<div class="accordion" id="detail-accordion">`.
- [x] 3.2 Create Panel 1 — **Fundamentals**: header "Fundamentals", default **expanded** (`show`). Move fundamentals card content (Market Cap, ATH/ATL, OHLC Source, Chain/Platform) inside.
- [x] 3.3 Create Panel 2 — **Chart**: header "Chart", default **collapsed**. Move the chart `<img>` (or "no chart" alert) inside.
- [x] 3.4 Create Panel 3 — **Strategy Controls**: header "Strategy Controls", default **expanded** (`show`). Move SMA/SL spinners, Position spinner, Find Best SMA button, and strategy summaries inside.
- [x] 3.5 Create Panel 4 — **Trades**: header "Trades", default **collapsed**. Move the unified trades table (or "no trades" message) inside.
- [x] 3.6 Create Panel 5 — **Performance**: header "Performance", default **collapsed**. Move performance stats table, resolution toggle, and lightweight-charts `<div id="perf-chart">` with its `<script>` inside.
- [x] 3.7 Create Panel 6 — **Place Order**: header "Place Order", default **collapsed**. Move the order form card inside.

## 4. Remove old tab branch conditionals

- [x] 4.1 Delete all `{% if tab == "chart" %}`, `{% elif tab == "performance" %}`, `{% elif tab == "fundamentals" %}`, `{% elif tab == "order" %}`, and the closing `{% endif %}` Jinja2 blocks.

## 5. Verify HTMX wiring

- [x] 5.1 Confirm each spinner (`sma-input`, `sma-high-input`, `sl-short-input`, `sl-long-input`, `pos-input`) still has correct `hx-include` referencing the consolidated hidden inputs.
- [x] 5.2 Confirm the Find Best SMA button still includes `#sl-short-input, #sl-long-input, #pos-input` and its `hx-on::after-request` redirect works.
- [x] 5.3 Confirm trade-row `hx-include` references are intact (`#sma-input, #pos-input, #tab-input` → update to remove `#tab-input` if needed, or leave as graceful no-op since the element no longer exists).
- [x] 5.4 Confirm Performance resolution-toggle buttons still include correct params.
