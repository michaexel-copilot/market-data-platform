## 1. Remove CSS

- [x] 1.1 Remove the `#INP_BEST_SMA_POS_USD` and `#INP_BEST_SMA_POS_USD:disabled` CSS rule blocks from the `<style>` section in `console.py`

## 2. Remove HTML

- [x] 2.1 Remove the `<input id="INP_BEST_SMA_POS_USD">` element from the `#ACTION_BAR` div in the HTML template in `console.py`
- [x] 2.2 Remove the `<button id="BTN_COMPUTE_BEST_SMA_V2">` element from the `#ACTION_BAR` div in the HTML template in `console.py`

## 3. Remove JavaScript

- [x] 3.1 Remove the `inpBestSmaPosUsd` and `btnBestSmaV2` variable declarations from the element-references section
- [x] 3.2 In `loadFundamentals`, remove `bestSmaRes` from the `Promise.all` destructure and remove the `fetch('/v1/trading-strategies/…/v2')` call (reduce from 4 to 3 parallel fetches)
- [x] 3.3 Remove the "BEST SMA Exit V1 section" `let bestSmaV2Html` block and the `if (bestSmaRes.ok)` branch inside `loadFundamentals`
- [x] 3.4 Remove the `best-sma-v2-section` div from the `fundamentalsPane.innerHTML` assignment at the end of `loadFundamentals`
- [x] 3.5 Remove `inpBestSmaPosUsd.disabled` and `btnBestSmaV2.disabled` assignments from `setActionsEnabled`
- [x] 3.6 Remove the entire `BTN_COMPUTE_BEST_SMA_V2` click event handler (`btnBestSmaV2.addEventListener(…)`)
- [x] 3.7 Remove the entire `_refreshBestSmaV2Section` async function

## 4. Tests

- [x] 4.1 Add a test in `test_api_rest.py` that fetches `GET /console` and asserts neither `INP_BEST_SMA_POS_USD` nor `BTN_COMPUTE_BEST_SMA_V2` appears in the response HTML
- [x] 4.2 Add a test in `test_api_rest.py` that fetches `GET /console` and asserts `best-sma-v2-section` does not appear in the response HTML
