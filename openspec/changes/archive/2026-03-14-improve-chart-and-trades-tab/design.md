## Context

The Chart & Trades tab has a single SMA period spinner (currently default 44) that controls all three SMA lines (High, Low, Close). The short-selling strategy uses the SMA Low line exclusively for entry/exit signals. The trades table already shows entry/exit prices and final P&L, but gives no information about price excursions that occurred while a trade was open — users cannot see how close a winning trade came to being stopped out, or whether a losing trade ever looked profitable.

Current state:
- `draw_chart.py::prepare_chart_data(sma_period)` computes SMA High/Low/Close all with the same period.
- `backtest_strategy()` records entry/exit/pnl per trade but no intra-period extremes.
- `web.py::asset_detail` accepts `sma: int = 44`, passes it through.
- Template has one SMA spinner; no independent SMA High control.

## Goals / Non-Goals

**Goals:**
- Add `max_adverse_pnl` / `max_favourable_pnl` to each closed trade in `backtest_strategy()`.
- Expose that data as a "Max Δ P&L" column in the trades table.
- Split the single SMA period into two: `sma` (Low, default 7) and `sma_high` (High, default 7).
- Rename the existing spinner label and adjust its Shift step to ±7.
- Add a second spinner for SMA High with identical keyboard behaviour.

**Non-Goals:**
- Changing the strategy logic (entry/exit/stop-loss rules stay the same).
- Tracking excursions using intraday highs/lows (daily close only, same as strategy).
- Persisting spinner values beyond the URL / hidden inputs.
- Modifying the SMA Close period independently.

## Decisions

### 1. Excursion metric uses daily close, not high/low

**Decision**: compute `max_adverse_pnl` / `max_favourable_pnl` from the daily **close** prices seen between entry and exit (inclusive of exit candle), not from the intraday high/low.

**Rationale**: The strategy itself is based on daily closes. Using intraday values would introduce inconsistency between the strategy signal and the excursion metric. The data already in memory is candle closes; no extra fetching or field access is required.

**Alternative considered**: use daily high for adverse excursion on shorts (worst case intraday). Rejected because it mixes different data granularities and would require an extra column pass.

### 2. Both excursion fields always present on closed trades; None for open trades

**Decision**: populate `max_adverse_pnl` and `max_favourable_pnl` for every closed trade. For open trades both are `None`.

**Rationale**: Keeps the template logic simple — it simply checks `trade.is_open`. No need for conditional exists checks.

### 3. Display logic: show adverse for profit trades, favourable for loss trades

**Decision**: In the "Max Δ P&L" column, show `max_adverse_pnl` (the worst moment) for profitable trades and `max_favourable_pnl` (the best moment) for loss trades. This answers the question "how close did I come to the opposite outcome?"

**Alternative considered**: always show both in two sub-columns. Rejected — too much table width for marginal information.

### 4. sma_high_period default = 7 (same as sma_period default change)

**Decision**: Both SMA Low and SMA High default to 7.

**Rationale**: Aligns with the feature request which specifies default 7 for both. Users can diverge them via the spinners.

### 5. `sma_period` URL parameter name unchanged; new `sma_high` added

**Decision**: Keep `sma` as the URL param for SMA Low period; add `sma_high` for the High period, both with default 7 in `web.py`.

**Rationale**: Zero breaking change to existing bookmarks / links. The rename is a UI label change only.

### 6. SMA Close continues to use `sma_period` (the Low period)

**Decision**: No third spinner is added; SMA Close follows the Low spinner.

**Rationale**: SMA Close is a visual reference line, not used by the strategy. Adding a third spinner is out of scope per the feature request.

## Risks / Trade-offs

- [Risk] Changing the default SMA period from 44 → 7 will regenerate charts on first load and may produce very different backtests for returning users.  
  → Mitigation: this is intentional per the feature request. The URL parameter is unchanged so bookmarks that explicitly set `sma=44` continue to work.

- [Risk] The excursion loop adds O(n_trades × holding_period) work to `backtest_strategy()`.  
  → Mitigation: the number of trades is small (≤ ~50 per year of daily data) and holding periods are short. No measurable latency impact expected.

- [Risk] Template grows another column, narrowing existing columns on small screens.  
  → Mitigation: the table already has a `max-height` scroll container; column widths auto-adjust. Acceptable trade-off.

## Migration Plan

1. Update `prepare_chart_data()` signature — backward-compatible (new kwarg with default).
2. Update `backtest_strategy()` — backward-compatible (new fields added to trade dicts).
3. Update `web.py` route — additive new query param with default.
4. Update template — additive column and new spinner.
5. No data migrations, no cache invalidation required; chart cache is keyed on symbol+sma period and will regenerate naturally on next request.

## Open Questions

*(none — all decisions resolved above)*
