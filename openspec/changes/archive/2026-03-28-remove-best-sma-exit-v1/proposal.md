## Why

The "Best SMA Exit V1" section in `PANE_FUNDAMENTALS` and its associated action-bar controls (`INP_BEST_SMA_POS_USD`, `BTN_COMPUTE_BEST_SMA_V2`) are dead UI — the feature was never specified in the management-console spec and no longer belongs in the console. Removing them reduces surface area and eliminates confusion.

## What Changes

- Remove `INP_BEST_SMA_POS_USD` (number input) and `BTN_COMPUTE_BEST_SMA_V2` (button) from the action bar HTML
- Remove CSS rules scoped to `#INP_BEST_SMA_POS_USD`
- Remove the `best-sma-v2-section` div and its `<h3>BEST SMA Exit V1</h3>` heading from `PANE_FUNDAMENTALS`
- Remove the `/v1/strategies/best-sma-exit-v1` API call from the parallel fetch in `loadFundamentals`
- Remove the `BTN_COMPUTE_BEST_SMA_V2` click event handler
- Remove the `_refreshBestSmaV2Section` helper function
- Remove the `inpBestSmaPosUsd` and `btnBestSmaV2` JS variable declarations
- Remove the enable/disable wiring for those variables in `setControlsEnabled`

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `management-console`: "Action button bar" requirement updated to explicitly state `INP_BEST_SMA_POS_USD` and `BTN_COMPUTE_BEST_SMA_V2` SHALL NOT be present; "Fundamentals detail pane" requirement updated to state the Best SMA Exit V1 section SHALL NOT be rendered

## Impact

- `src/market_data/api/rest/console.py` — all changes confined here
- No API changes, no schema changes, no test additions required
- The spec for `management-console` is unaffected (Best SMA was never specced)
