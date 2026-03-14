## Context

The Chart & Trades tab has two independent SMA period spinners (SMA LOW / SMA HIGH) that users tune manually. The short strategy uses SMA LOW as its entry signal; the long strategy uses SMA HIGH. Finding the optimal pair for a given symbol requires iterating over hundreds of (sma_low, sma_high) combinations — a task that fits naturally into a backend endpoint backed by the existing `backtest_short_strategy` / `backtest_long_strategy` functions.

The OHLCV data is already cached to disk per (source, date) by `prepare_chart_data`.  
The brute-force search itself is CPU-bound (pure Python loops), takes ~0.5–3 s for a typical range, and only needs to run once per (symbol, date) — the result is small (two integers) and safe to cache in process memory or to a JSON file.

Short and long trade tables are currently rendered in two separate, tab-switched panels with duplicated template markup. Merging them improves the overview and reduces template duplication.

---

## Goals / Non-Goals

**Goals:**

- Add a "Find Best SMA" button on the Chart & Trades tab.
- Implement a `/asset/{symbol}/best-sma` HTMX endpoint that iterates SMA LOW ∈ [3, 50] × SMA HIGH ∈ [3, 50] (step 1), scores each pair by *average closed-trade P&L per trade* across both strategies combined, and returns the winning (sma_low, sma_high).
- Cache the search result in-process (dict keyed by `(symbol, date)`) so repeat clicks are instant.
- On success, the response triggers the main `#detail-pane` refresh with the optimized SMA values pre-filled so both spinners and the chart update immediately.
- Merge the two separate strategy trade tables into one combined table with a "Dir" column; short rows → light red background (#ffe8e8); long rows → light green background (#e8f5e8). P&L and Max-Delta-P&L columns are NOT colorized per direction (they keep their existing success/danger text colour).
- Show combined strategy summaries (count, total P&L, avg P&L) for short and long above the unified table, always visible regardless of which direction has more trades.
- Place SMA LOW and SMA HIGH spinners side by side in one row, with each spinner's corresponding SL % field directly beneath it.

**Non-Goals:**

- Optimizing stop-loss percentages (only SMA periods are searched).
- Persisting the cache across server restarts (in-memory only).
- Pagination or sorting of the merged trade table.
- Changing the scoring metric (always avg P&L/trade of *closed* trades only; open trades excluded).

---

## Decisions

### Decision: In-process dict cache (not disk)
The result is two integers. A `dict` keyed by `(symbol, date.today())` is sufficient; old dates never hit because the OHLCV data changes daily anyway. Disk JSON would add file-I/O complexity for no benefit.

### Decision: Grid range [3, 50], step 1
Covers practical SMA periods (3–50) with 48 × 48 = 2 304 combinations. Runtime is acceptable (~1–4 s). The range is hard-coded as constants; no user configuration needed.

### Decision: Score = combined avg closed-trade P&L per trade
`score = (sum_short_closed_pnl + sum_long_closed_pnl) / (n_short_closed + n_long_closed)` — identical to what the current per-strategy summary lines display. Ties broken by higher total P&L. If either strategy has zero closed trades for a combination the score contribution is 0.

### Decision: Response via full `#detail-pane` redirect (hx-get)
After the best-SMA endpoint returns the winning values, the button's HTMX trigger fires a second `hx-get` on `#detail-pane` with the new `sma` and `sma_high` query params. This reuses all existing rendering logic with no extra partial templates.

Alternative considered: OOB swap to update only spinner values. Rejected because it leaves the chart stale and requires maintaining a separate spinner partial.

### Decision: SMA spinner side-by-side via Bootstrap grid row
Two `col` divs inside a `row` hold (SMA LOW spinner + SL Short %) and (SMA HIGH spinner + SL Long %) respectively. The "Find Best SMA" button is placed in the same panel, below the spinners row.

### Decision: Unified trade table — both directions always shown
The `strategy_tab` toggle (Short / Long) is replaced by a single merged table that always displays both directions, sorted by entry date descending. This removes the tab state and simplifies the template.

---

## Risks / Trade-offs

- **Long search time on slow hardware**: 2 304 iterations × 2 backtests each may take 5–8 s on a slow machine. Mitigation: the button shows a spinner while loading (HTMX `htmx-request` indicator); the result is cached.
- **merged table may be long**: Assets with many years of OHLCV history can produce 100+ combined rows. Mitigation: existing `max-height:70vh; overflow-y:auto` scroll container is retained.
- **SMA range hard-coded**: Users with unusual assets (very low-volatility coins) might benefit from wider ranges. Mitigation: out of scope; can be added as a follow-up feature.

---

## Migration Plan

1. Update `web.py`: add `BEST_SMA_CACHE` dict, add `/asset/{symbol}/best-sma` route.
2. Update `templates/asset_detail.html`:
   a. Refactor spinner layout to side-by-side.
   b. Add "Find Best SMA" button.
   c. Merge short + long trade tables into unified table with Dir column and row-level background colours.
   d. Add dual summary section above the table.
   e. Remove `strategy_tab` toggle buttons (no longer needed).
3. Update `web.py` `asset_detail()` handler: merge trades lists for the template context (already passed separately; still needed for the merged table template logic).
4. No database migration needed.

## Open Questions

- None. All design points resolved in proposal review.
