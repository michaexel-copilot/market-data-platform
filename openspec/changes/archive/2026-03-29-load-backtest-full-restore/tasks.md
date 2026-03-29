## 1. Backend: list_cache filename injection

- [x] 1.1 Update `list_cache(symbol)` in `backtest_engine.py` to inject `_filename` (bare filename, e.g. `BTC_sma_sma_long_cash_abc123.json`) into each returned dict

## 2. Backend: cached results endpoint

- [x] 2.1 Add `GET /asset/{symbol}/backtest-cache/file/{filename}/results` route to `web.py` — load the file from `cache/backtest/{filename}`, extract `_params` and result data, render `backtest_results.html`
- [x] 2.2 Return a friendly HTML error partial if the file does not exist (not a 500)

## 3. Template: Load button data attributes

- [x] 3.1 Add `data-best-ind1-period="{{ bp.ind1_period or 1 }}"` and `data-best-ind2-period="{{ bp.ind2_period }}"` to the Load button in `backtest_history.html`
- [x] 3.2 Add `data-results-url="/asset/{{ symbol }}/backtest-cache/file/{{ r._filename }}/results"` to the Load button

## 4. JS: loadBacktestParams restore behaviour

- [x] 4.1 In `loadBacktestParams()` (in `backtest_history.html`), set `#ind1-min` and `#ind1-max` both to `d.bestInd1Period`, and `#ind2-min` and `#ind2-max` both to `d.bestInd2Period`
- [x] 4.2 After setting form fields, call `htmx.ajax('GET', d.resultsUrl, {target: '#backtest-results', swap: 'innerHTML'})` to populate the results panel
