## Context

The asset detail page currently has a split interaction model where chart information appears in a separate accordion item and validation trades are detached from cached backtest results. Users primarily work from cached backtests and need an analysis-first view that keeps the backtest table, validation trades, and performance chart in one contiguous flow.

The change affects frontend layout and interaction behavior in the management console:
- remove the standalone chart accordion item;
- reposition validation trades directly under cached backtests;
- auto-open `Performance` after cached-backtest load paths;
- render a 1-day performance chart that overlays indicators and price using a context window based on trade timing.

Constraints:
- keep current backtest load entry points (Load button and post-run load);
- preserve existing backend data contracts where possible;
- avoid introducing new charting dependencies unless required by existing UI code.

## Goals / Non-Goals

**Goals:**
- Make asset-detail analysis flow backtest-centric and faster to scan.
- Ensure the user lands directly in `Performance` after loading a cached backtest.
- Provide a deterministic chart time-window strategy:
  - start 5 days before the opened trade when trade context exists;
  - otherwise show at least the last 30 days through today.
- Keep price and indicator series aligned on daily granularity.

**Non-Goals:**
- Redesign unrelated accordion sections or global console navigation.
- Change strategy/backtest computation logic or cached backtest storage format.
- Introduce intraday charting or new interval controls in this change.

## Decisions

### Decision: Consolidate analysis sections under cached backtests

Validation Trades will be rendered immediately below the Cached Backtests table, and the separate `Chart & Trades: Chart` accordion item will be removed.

Rationale:
- keeps related artifacts (selected backtest, validation outputs, performance visual) in one vertical reading flow;
- reduces accordion hopping and cognitive load.

Alternative considered:
- keep existing section order and only auto-scroll to chart.
- rejected because it preserves fragmented layout and weaker discoverability.

### Decision: Event-driven post-load behavior for `Performance`

Both cached-backtest load entry points will emit/trigger one shared post-load handler that:
- opens `Performance` accordion;
- computes chart window;
- re-renders chart with current backtest payload.

Rationale:
- avoids duplicated logic and drift between "Load" and "new run" flows;
- ensures consistent UX regardless of load source.

Alternative considered:
- duplicate logic in both handlers.
- rejected due to maintenance and regression risk.

### Decision: Deterministic chart-window selection

Window selection algorithm:
1. If an opened trade timestamp exists, set `start = opened_trade_ts - 5 days`, `end = today`.
2. Else set `start = today - 30 days`, `end = today`.
3. If rule (1) yields less than 30 calendar days, extend to at least 30 days.
4. Aggregate/plot on 1-day basis for both price and indicators.

Rationale:
- preserves trade context when available while guaranteeing sufficient trend history.

Alternative considered:
- fixed 30-day window for all cases.
- rejected because it weakens pre-trade context for short-lived or recently opened positions.

### Decision: Reuse existing chart stack

Implementation should reuse the current chart rendering utilities/components used by the asset detail page where possible.

Rationale:
- minimizes risk and implementation time;
- avoids new dependency and bundle-size impact.

Alternative considered:
- add a new chart library for the performance panel.
- rejected unless existing stack cannot support price + indicator overlay.

## Risks / Trade-offs

- [Incorrect trade timestamp parsing] → Mitigation: normalize timestamps at load boundary and add UI-level guard/fallback to 30-day mode.
- [Missing indicator series for selected backtest] → Mitigation: render price-only chart with visible warning badge in `Performance`.
- [Accordion state race between async load and UI updates] → Mitigation: invoke post-load handler only after backtest payload is committed to state.
- [Chart range mismatch between price and indicator datasets] → Mitigation: compute one canonical date index and align all series before plotting.
