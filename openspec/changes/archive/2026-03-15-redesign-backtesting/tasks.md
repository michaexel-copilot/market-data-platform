## 1. Backend – Optimisation split

- [x] 1.1 Remove `BEST_SMA_CACHE` global dict and its type annotation from `web.py`
- [x] 1.2 In `_find_best_sma`: remove cache lookup (`if cache_key in BEST_SMA_CACHE`) and cache store (`BEST_SMA_CACHE[cache_key] = best_pair`)
- [x] 1.3 In `_find_best_sma`: compute `split_idx = int(len(candles) * 0.8)` and slice `candles` to `candles[:split_idx]` before extracting `closes`, `highs`, `lows`
- [x] 1.4 In `_find_best_sma`: return `best_pair` along with `split_idx` (or the training slice end date) so the caller can derive the validation slice — or return the full original candles + split_idx via a refactored signature

## 2. Backend – Validation backtest

- [x] 2.1 In the best-sma route handler (after calling `_find_best_sma`): slice the full candle list to `candles[split_idx:]` to get the validation slice
- [x] 2.2 Compute SMA arrays for the winning pair on the validation slice
- [x] 2.3 Run `backtest_short_strategy` and `backtest_long_strategy` on the validation slice with the winning SMA values
- [x] 2.4 Build `out_of_sample_short_summary` dict: `{count, total_pnl, avg_pnl}` from closed trades only
- [x] 2.5 Build `out_of_sample_long_summary` dict: `{count, total_pnl, avg_pnl}` from closed trades only
- [x] 2.6 Compute date-range strings: `train_date_from`, `train_date_to`, `val_date_from`, `val_date_to` from candle dicts
- [x] 2.7 Pass all six new variables to the template context in the best-sma route response

## 3. Template – In-sample / out-of-sample display

- [x] 3.1 Add `train_date_from` / `train_date_to` label to the existing in-sample summary block (e.g. "In-Sample (Optimisation): 2020-01-01 → 2024-04-15")
- [x] 3.2 Add a visually separated "Out-of-Sample (Validation)" block below the in-sample summary, guarded by `{% if out_of_sample_short_summary %}`
- [x] 3.3 Inside the validation block: show date range (`val_date_from` → `val_date_to`), short trade count/total P&L/avg P&L, long trade count/total P&L/avg P&L
- [x] 3.4 Ensure the two sections are clearly visually separated (e.g. a horizontal rule, distinct background, or labelled card headers)
