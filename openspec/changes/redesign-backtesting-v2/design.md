## Context

The current `#heading-strategy-controls` accordion hardcodes an SMA LOW / SMA HIGH / Stop-Loss crossover strategy. It drives `backtest_short_strategy` and `backtest_long_strategy` from `draw_chart.py` (hand-rolled, no external backtest library). The Find Best SMA optimiser already exists (`/asset/{symbol}/best-sma`) and does a 50×50 grid search on training data.

The redesign replaces this fixed UI with a flexible indicator-selector (Price / SMA / EMA for Indicator 1; SMA / EMA for Indicator 2), an Exposure dropdown (Long+Cash / Short+Cash / Long+Short), adjustable train/validation date splits, and a `backtesting.py`-powered optimiser that sweeps the configured period ranges and surfaces the best parameters.

Existing `backtest_short_strategy` / `backtest_long_strategy` functions are retained for the chart-rendering path; they are NOT replaced.

**Constraints:**
- FastAPI + HTMX + Jinja2 stack; no SPA framework.
- `backtesting.py` is not yet installed (add to `pyproject.toml`).
- Data is fetched from EODHD / CoinGecko / Yahoo Finance and cached per-day in `cache/`.
- Python 3.14+, `uv` package manager.

---

## Goals / Non-Goals

**Goals:**
- Replace strategy-controls accordion body with indicator/exposure/date-range inputs and a "Run Backtest" button.
- Use `backtesting.py` + its built-in `Backtest.optimize()` for parameter sweep on training data.
- Split data at a user-adjustable cutoff (default: train ≤ 2024-12-31, validate ≥ 2025-01-01).
- Display best parameters, P&L summary for both periods, and a trade table for the validation period.
- Cache backtest results to disk; allow manual invalidation.

**Non-Goals:**
- Replacing the existing chart, OOS summary, or trade-table rendering for the SMA-crossover strategy currently wired to the chart panel.
- Real-time streaming of backtest progress.
- Per-strategy stop-loss or position-size tuning (out of scope for this redesign).

---

## Decisions

### D1 — Use `backtesting.py` `Backtest.optimize()` for the grid search

**Decision:** Implement a generic `CrossoverStrategy` using the `backtesting.py` Strategy API. Use `Backtest.optimize()` to sweep indicator periods on training data rather than writing a nested loop ourselves.

**Rationale:** `backtesting.py` provides vectorised execution, a well-tested `Strategy` base class, and `optimize()` with grid-search built-in. Writing equivalent code from scratch was the source of bugs in the earlier SMA optimiser.

**Alternative considered:** Keep hand-rolled backtest (like current `backtest_short_strategy`). Rejected — `backtesting.py` removes reinventing broker simulation, handles edge cases (open-at-close, partial fills, etc.), and is the stated requirement.

**backtesting.py input format:** Convert `list[dict]` candles → `pandas.DataFrame` with `DatetimeIndex` and columns `Open, High, Low, Close, Volume`.

---

### D2 — Indicator computation inside `backtesting.py` Strategy via `self.I()`

**Decision:** Define `SMA` and `EMA` indicators inside the Strategy class using `self.I(talib_or_numpy_fn)` / `pd.Series.rolling().mean()` / `pd.Series.ewm().mean()`. `Price` (Indicator 1 = close) is represented as `self.data.Close`.

**Rationale:** `self.I()` is the idiomatic approach; it integrates with `optimize()` correctly and avoids manual array slicing.

**Period range convention:**
- If Indicator 1 = Price → no period; only Indicator 2 period is swept.
- If Indicator 1 = SMA/EMA AND Indicator 2 = SMA/EMA → both periods swept independently.
- Default sweep range for any SMA/EMA period: 1–200 (step 1), configurable via UI inputs.

---

### D3 — Exposure modes implemented as three Strategy subclasses

**Decision:** Implement three `backtesting.py` Strategy subclasses: `LongCashStrategy`, `ShortCashStrategy`, and `LongShortStrategy`. A factory function selects the right class based on the `exposure` parameter.

**Rationale:** Trying to encode all three modes in one class with `if` branches makes `optimize()` results harder to interpret and adds noise to the trade log.

---

### D4 — Holding period + signal blackout via trade-entry guard

**Decision:** Enforce "hold ≥ 1 day, ignore signals for 24 h" by tracking an `entry_bar` index inside the Strategy. A new signal is acted on only if `current_bar - entry_bar >= 1`.

**Rationale:** `backtesting.py` processes one bar at a time; an integer counter is the simplest guard.

---

### D5 — Date-split done by slicing the DataFrame before passing to `Backtest`

**Decision:** Slice the candle DataFrame into `df_train` (rows with `date <= train_end`) and `df_val` (rows with `date >= val_start`) before constructing `Backtest` objects. Optimisation runs on `df_train`; final evaluation runs on `df_val` with the winning parameters.

**Rationale:** Clean separation — no filtering logic inside the Strategy class.

---

### D6 — Cache as JSON files in `cache/backtest/`

**Decision:** Cache key = `{SYMBOL}_{ind1}_{ind2}_{exposure}_{train_end}_{val_start}.json`. File contains: best parameters, training stats, validation stats, validation trade list. Invalidated by deleting the file; a "Clear Cache" button on the UI sends `DELETE /asset/{symbol}/backtest-cache`.

**Rationale:** Consistent with existing day-scoped OHLCV caches already used in the project. No database dependency.

---

### D7 — `/indicators` and `/exposures` endpoints return JSON for `<select>` population

**Decision:** Two new GET endpoints hardcode the option lists (no DB):
- `GET /indicators` → `[{"id": "price", "label": "Price"}, {"id": "sma", "label": "Simple Moving Average (SMA)"}, ...]`
- `GET /exposures` → `[{"id": "long_cash", "label": "Long+Cash"}, ...]`

These are fetched once on page load via HTMX `hx-trigger="load"` and cached in the browser.

---

### D8 — `backtesting.py` is added as a project dependency

**Decision:** Add `backtesting>=0.3.3` to `pyproject.toml` `[project.dependencies]` and install via `uv sync`.

**Rationale:** Required by D1. No conflict with existing deps.

---

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| `backtesting.py` optimize() is slow for large ranges (1–200 × 1–200 = 40 000 combinations) | Default range shown in UI is 1–200 but users are guided to narrow it. Progress indication via HTMX loading state. Consider capping at 100 per axis in the backend if > 10 000 combos. |
| `backtesting.py` requires `pandas` ≥ 1.3 | `yfinance` already depends on pandas; no conflict expected. Verify with `uv sync`. |
| Existing `find-best-sma` endpoint becomes orphaned | Keep endpoint for one cycle; mark deprecated in code comment. Remove in a follow-up change. |
| Cache grows unbounded | Files are small enough (< 50 KB each). Acceptable for now. TTL or manual clear via UI button. |
| `Price` as Indicator 1 with only 1 period parameter means the grid reduces to 1D | Handled in backend: skip Indicator 1 period param when `ind1 = price`. |

---

## Migration Plan

1. Install `backtesting` via `uv add backtesting`.
2. Create `cache/backtest/` directory (auto-created on first write).
3. Add backend module `backtest_engine.py` with `CrossoverStrategy` classes and `run_backtest()` + `optimize_and_validate()` functions.
4. Add `/indicators`, `/exposures` GET endpoints and `/asset/{symbol}/backtest` POST + DELETE endpoints in `web.py`.
5. Replace `#collapse-strategy-controls` body in `asset_detail.html` with new indicator/exposure/date inputs and results placeholder.
6. No database migrations required.
7. No change to existing chart endpoints; rollback = revert HTML accordion body + remove new routes.

---

## Open Questions

- **Q1:** Should `backtesting.py`'s built-in broker simulation (commission, slippage) be enabled? Currently hand-rolled strategies in `draw_chart.py` ignore commission. → Recommend disabling (`commission=0`) to match existing behaviour; can be enabled later.
- **Q2:** What position sizing should `backtesting.py` use? Fixed fractional (e.g. 99% of equity) is simplest. → Use `self.buy(size=0.99)` / `self.sell(size=0.99)`.
- **Q3:** For `Long+Short`, should both legs run simultaneously or sequentially? `backtesting.py` does not allow concurrent long+short in a single Strategy without `exclusive_orders=True` workaround. → Use the `LongShortStrategy` subclass that manages positions explicitly; or use two separate `Backtest` runs and merge the trade logs.
