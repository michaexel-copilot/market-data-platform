## Why

The asset detail page currently shows a chart accordion item that is redundant and places validation-trade information away from the cached backtest results it belongs to. This makes the page harder to scan and slows down analysis when users load a cached backtest or run a new one.

## What Changes

- Remove the accordion item `Chart & Trades: Chart` from the asset detail page.
- Move the Validation Trades section to sit directly under the Cached Backtests table.
- When a cached backtest is loaded (via Load button or after a new backtest run), automatically open the `Performance` accordion item.
- Add a performance chart inside `Performance` that overlays indicators and price on a 1-day basis.
- Use a chart time window of either:
  - 5 days before the opened trade through today, or
  - at least the last 30 days through today when trade-based context is unavailable.

## Capabilities

### New Capabilities
- `asset-detail-performance-view`: UI behavior for performance-focused layout and charting in the asset detail page after cached backtest load.

### Modified Capabilities
- `management-console`: Asset detail page layout and interaction requirements are updated (accordion behavior, section order, and performance chart rendering on cached backtest load).

## Impact

- Frontend/UI components for the asset detail page layout and accordion interactions.
- Cached backtest load flow and post-load focus behavior.
- Performance chart rendering logic (price + indicator overlay, daily granularity, dynamic time window selection).
- Potential updates to UI tests that assert panel order, default open section, and chart visibility after load actions.
