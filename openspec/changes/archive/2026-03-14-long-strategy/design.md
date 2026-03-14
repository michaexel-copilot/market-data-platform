## Context

The app has a single short strategy backtest (`backtest_strategy()` in `draw_chart.py`) with a hardwired 10% stop loss. The chart can highlight one trade at a time (a single `highlight` dict). The "Chart & Trades" section renders one trades table with a single summary bar.

This change adds a mirrored long strategy, makes stop loss configurable per strategy, introduces Short/Long sub-tabs, and allows both chart highlights to coexist independently.

## Goals / Non-Goals

**Goals:**
- Mirror the short strategy to a long strategy using SMA High as the signal line
- Configurable stop loss % per strategy (separate URL params + UI spinners)
- Short/Long sub-tabs inside "Chart & Trades"; each with its own summary bar and trades table
- Two independent chart highlights (short: blue/orange; long: green/red) that overlap
- Sub-tab state preserved through HTMX partial reloads

**Non-Goals:**
- Intraday or non-daily backtest frequencies
- Persistent user settings (beyond URL params in the current session)
- Combined P&L reporting across both strategies

## Decisions

### 1 — Rename `backtest_strategy` → `backtest_short_strategy`

Add `stop_loss_pct: float = 0.10` parameter. Avoids a breaking change elsewhere because `web.py` is the only caller — update it simultaneously. The rename makes intent explicit and is worth the one-line callsite change.

*Alternative considered*: add a `direction` enum param to one function. Rejected: the two strategies have enough divergence in signal logic and P&L formula that separate functions are clearer.

### 2 — New `backtest_long_strategy(candles, sma_high, position_size_usd, stop_loss_pct)`

Mirrors `backtest_short_strategy` with flipped logic:
- Entry: `close[i] > sma_high[i]` AND `close[i-1] <= sma_high[i-1]`
- Stop: `close <= entry × (1 - stop_loss_pct)` → exit at stop price (loss)
- Take profit: `sma_high[i] > entry_price` AND `close[i] >= sma_high[i]` → exit at `sma_high[i]` (profit)
- P&L: `(exit_price - entry_price) / entry_price × position_size_usd`
- Excursion: `max_adverse_pnl` = worst running P&L (price fell); `max_favourable_pnl` = best running P&L (price rose)

### 3 — `draw_chart()` gains `hl_short` and `hl_long` optional dicts

Replace the single `highlight` parameter with two independent ones. Each renders its own crosshair pair:
- `hl_short`: blue entry / orange exit (unchanged from current highlight)
- `hl_long`: green entry / red exit (new)

Chart filename includes both highlight indices and both SL values so caching stays correct:
`{symbol}_SMAl{n}_SMAh{m}_SLs{x}_SLl{y}_hs{i}_hl{j}.png`

### 4 — URL params for all new inputs

| Param | Type | Default | Description |
|---|---|---|---|
| `sl_short` | float | 0.10 | Stop loss % for short strategy |
| `sl_long` | float | 0.10 | Stop loss % for long strategy |
| `hl_short` | int \| None | None | Short trade highlight index |
| `hl_long` | int \| None | None | Long trade highlight index |
| `strategy_tab` | str | "short" | Active sub-tab ("short" or "long") |

### 5 — Sub-tab nav as simple Bootstrap pills; state via hidden input

Two pill buttons (`short` / `long`) inside the Chart & Trades partial. Active tab is driven by a hidden `<input id="strategy-tab-input" name="strategy_tab">` that is included in every spinner's `hx-include`. Clicking a sub-tab button fires an HTMX request with `strategy_tab=short/long`, preserving the chart and SMA state. No JavaScript tab state needed — the server renders the correct active tab from the URL param.

### 6 — Stop loss spinners: same keyboard handler as SMA spinners

±1 / Shift ±5 / Ctrl+Shift ±10. Range: 1–50 (%). Values stored as integers in the UI (e.g. `10` = 10%) and divided by 100 when passed to the backtest functions. This avoids float parsing issues in the URL.

*Alternative*: store as decimal (0.10). Rejected: the spinner would show `0.1` which is awkward UX; integer % is cleaner.

### 7 — Hidden inputs threaded through all HTMX chains

Every `hx-include` across all tabs (SMA spinners, position spinner, trade row clicks) must include:
`#sl-short-input, #sl-long-input, #strategy-tab-input, #hl-long-input`

On non-chart tabs (Performance, Fundamentals, Order), hidden `<input>` elements for all these params are added alongside the existing `#sma-high-input`.

## Risks / Trade-offs

- **Chart file naming**: filename grows longer with both SL values + both highlight indices. Not an issue for the file system; cached files from before the change use a different naming pattern so they'll be regenerated on first load.
- **Two backtest calls**: each page load now runs two backtests. Both are O(N) over ~365 candles — negligible.
- **Tab switching clears the chart highlight of the other strategy**: it doesn't — `hl_short` and `hl_long` are independent URL params, so switching sub-tabs preserves both highlights as long as hidden inputs are threaded correctly.
- **Stop loss as integer %**: `sl_short=10` means 10%. The web.py route converts: `stop_loss_pct = sl_short / 100.0`.

## Open Questions

None — all design decisions settled in the explore session.
