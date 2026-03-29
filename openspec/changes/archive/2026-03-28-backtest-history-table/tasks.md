## 1. Cache layer

- [x] 1.1 Add `_params` embedding to `save_cache()` in `backtest_engine.py` — store symbol + all kwargs under a `_params` key inside the saved JSON
- [x] 1.2 Add `list_cache(symbol: str) -> list[dict]` to `backtest_engine.py` — glob `cache/backtest/{SYMBOL}_*.json`, load each file, skip files without `_params`, return list sorted newest-first by file mtime

## 2. Backend endpoint

- [x] 2.1 Add `GET /asset/{symbol}/backtest-history` route to `web.py` — calls `list_cache(symbol)`, passes results to `backtest_history.html` template
- [x] 2.2 Handle empty results: pass an empty list so the template can render an empty-state message

## 3. Frontend template

- [x] 3.1 Create `templates/backtest_history.html` partial — render a Bootstrap table with columns: Train Start, Train End, Val Start, Ind 1, Ind 2, Exposure, Train Net P&L, Val Net P&L, Val Trades, Load
- [x] 3.2 Color-code Val Net P&L: green for positive, red for negative
- [x] 3.3 Add "Load" button per row using `onclick` JS that reads `data-*` attributes and populates `#ind1-type`, `#ind2-type`, `#ind1-min`, `#ind1-max`, `#ind2-min`, `#ind2-max`, `#exposure`, `#train-start`, `#train-end`, `#val-start`
- [x] 3.4 Add empty-state message when no cached runs exist

## 4. HTMX wiring in asset_detail.html

- [x] 4.1 Add `<div id="backtest-history" hx-get="/asset/{symbol}/backtest-history" hx-trigger="intersect once">` below `#run-backtest-btn`
- [x] 4.2 Add `hx-on::after-request="htmx.trigger('#backtest-history', 'refresh')"` (or equivalent) to the Run Backtest button so the history table reloads after a successful POST
