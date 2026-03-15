## Context

`_find_best_sma` in `web.py` runs a grid search over SMA LOW × SMA HIGH ∈ [3,50] using all available OHLCV candles. The winning pair is selected purely based on in-sample performance, which overstates expected real-world results. An in-process dict keyed by `(symbol, date)` caches the result for the day.

The Chart & Trades accordion currently shows a two-line "dual strategy summary" (trade count, total P&L, avg P&L) above the unified trade table, covering all candles.

## Goals / Non-Goals

**Goals:**
- Split candles 80/20 (chronological) inside `_find_best_sma` so optimisation only sees the training window.
- Remove the in-process day cache so the computation is always fresh (cache was per-day; the new logic changes the data used, so any stale cache entry would produce wrong results).
- After the best-SMA route resolves, run a second backtest on the validation slice (last 20 %) and surface those results in the UI as a clearly separated section.
- Show date ranges for both the training and validation windows.

**Non-Goals:**
- No change to the full candle backtest used for the chart or the unified trade table.
- Not persisting validation results to disk.
- Not exposing the split ratio as a user-configurable parameter.
- No change to `perf_data.py` or the Performance accordion.

## Decisions

### D1 — 80/20 split inside `_find_best_sma`, not a separate function
The split is a concern of the optimisation process, not of `backtest_short_strategy` / `backtest_long_strategy`. Keeping it inside `_find_best_sma` avoids leaking the concept to callers.

*Alternative considered:* a generic `split_candles(candles, train_pct)` helper. Rejected — one-time use, adds indirection without benefit.

### D2 — Remove `BEST_SMA_CACHE` entirely
The cache was valid when all candles were used (result was stable within a day). Now the training candle count grows daily, so even a same-day cache would be stale if candles are refreshed. Removing it is simpler and correct; the grid search is fast enough (< 2 s typically) that caching buys little.

*Alternative considered:* keep cache but key by `(symbol, len(candles))`. Rejected — adds complexity with marginal gain.

### D3 — Validation backtest runs in the best-sma route handler, not in `_find_best_sma`
`_find_best_sma` returns `(sma_low, sma_high)`. Mixing validation concerns inside it would break the single-responsibility. The route handler already assembles context for the template; it can run the validation backtest and pass results to the template.

### D4 — Pass validation summary as `out_of_sample` context variable to existing template
Two new template variables `out_of_sample_short_summary` and `out_of_sample_long_summary` carry the validation results, mirroring the existing `s_total` / `l_total` variables. The template renders them in a clearly labelled block immediately after the existing in-sample summary.

### D5 — Date range from first/last candle date in each slice
The training window is `candles[0].date … candles[split_idx-1].date`; validation is `candles[split_idx].date … candles[-1].date`. Dates are already stored as `datetime.date` objects on each candle dict.

## Risks / Trade-offs

- **Validation results only shown after "Find Best SMA"**: if the user sets SMA values manually and never clicks the button, the out-of-sample section will not appear. This is acceptable — validation is tightly linked to the optimisation flow.
  → *No mitigation needed; document in UI labels.*

- **Split boundary shifts daily**: as new candles arrive, the 80/20 boundary moves by one candle per day, so the validation window gradually shrinks from the front. This is a known limitation of a fixed-ratio split on a growing dataset.
  → *Acceptable; the date-range display makes this transparent to the user.*

- **Template receives `None` validation results when best-SMA not yet run**: guard with `{% if out_of_sample_short_summary %}` in the template.

## Migration Plan

1. Edit `_find_best_sma` in `web.py`: remove cache dict + lookup/store; slice candles at 80 %
2. Edit best-sma route handler in `web.py`: run validation backtest and pass summary dicts + date-range strings to the template context
3. Edit `asset_detail.html`: add out-of-sample summary block with date-range headers
4. Remove `BEST_SMA_CACHE` global dict (and any imports that become unused)
5. Manual smoke test: click "Find Best SMA" on one asset; verify both summary sections appear with correct date ranges
