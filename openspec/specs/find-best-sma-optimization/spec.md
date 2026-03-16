## ADDED Requirements

### Requirement: Find Best SMA button triggers optimization search
A **"Find Best SMA"** button SHALL be present on the Chart & Trades tab, adjacent to the SMA spinners. Clicking it SHALL send an HTMX GET request to `/asset/{symbol}/best-sma` passing the current `sl_short`, `sl_long`, `pos`, and `network` values. While the request is in flight the button SHALL show a loading indicator.

#### Scenario: Button is present on chart tab
- **WHEN** the Chart & Trades tab is active
- **THEN** a "Find Best SMA" button SHALL be visible near the SMA spinners

#### Scenario: Button triggers HTMX request
- **WHEN** the user clicks "Find Best SMA"
- **THEN** an HTMX GET request SHALL be sent to `/asset/{symbol}/best-sma` with current `sl_short`, `sl_long`, `pos`, and `network` query parameters

#### Scenario: Loading indicator during search
- **WHEN** the HTMX request is in flight
- **THEN** the button SHALL display a loading indicator (spinner or disabled state)

---

### Requirement: Backend endpoint searches SMA grid
The `/asset/{symbol}/best-sma` endpoint SHALL iterate SMA LOW ∈ [3, 50] and SMA HIGH ∈ [3, 50] (step 1, inclusive), run `backtest_short_strategy` and `backtest_long_strategy` for each combination, and score each pair as the **average closed-trade P&L per trade** across both strategies combined.

The grid search SHALL use only the **first 80 % of available OHLCV candles** (chronologically, integer floor). The winning (sma_low, sma_high) pair is the one with the highest combined score. If the total number of closed trades across both strategies is zero for a given pair, that pair's score SHALL be treated as negative infinity.

#### Scenario: Grid covers range 3–50 inclusive
- **WHEN** the best-sma search is run for any symbol
- **THEN** all integer combinations (sma_low, sma_high) with sma_low ∈ [3,50] and sma_high ∈ [3,50] SHALL be evaluated

#### Scenario: Score computed from closed trades only
- **WHEN** a (sma_low, sma_high) pair is scored
- **THEN** only trades where `is_open == False` and `pnl is not None` SHALL contribute to the average

#### Scenario: Only training candles used for scoring
- **WHEN** the grid search runs
- **THEN** only the first `floor(len(candles) * 0.8)` candles (chronological order) SHALL be passed to `backtest_short_strategy` and `backtest_long_strategy` during scoring

#### Scenario: Winning pair returned in JSON
- **WHEN** the search completes
- **THEN** the endpoint SHALL return a JSON response `{"sma": <int>, "sma_high": <int>}` with the winning values

#### Scenario: Fallback to local computation when precomputed data absent
- **WHEN** the market-data-platform returns HTTP 404 for the requested symbol
- **THEN** the endpoint SHALL run the local `_find_best_sma()` grid search and return its result

#### Scenario: Precomputed data used when available
- **WHEN** the market-data-platform returns HTTP 200 with `best_sma` strategy data for the symbol
- **THEN** the endpoint SHALL use the precomputed `sma_low` and `sma_high` values without running the local grid search

---

### Requirement: Spinner values updated after search
The HTMX response from `/asset/{symbol}/best-sma` SHALL cause the main `#detail-pane` to reload with the winning `sma` and `sma_high` values applied, so both spinners and the chart reflect the optimized pair.

#### Scenario: Detail pane reloads with optimized SMA values
- **WHEN** the best-sma response is received
- **THEN** the `#detail-pane` SHALL reload at `/asset/{symbol}` with `sma=<winning_low>&sma_high=<winning_high>` (plus all other current parameters preserved)

---

### Requirement: Auto-trigger fires exactly once per ticker selection
When a user selects a ticker (click or keyboard), the "Find Best SMA" button SHALL be triggered exactly once after the detail pane finishes loading. Re-entrant calls to `activateItem` during the same activation cycle SHALL be suppressed via a guard flag so that only one `MutationObserver` is registered per activation.

#### Scenario: Single trigger on click
- **WHEN** the user clicks a ticker in the asset list
- **THEN** the "Find Best SMA" button SHALL be clicked exactly once after the detail pane loads

#### Scenario: No double-trigger on repeated activation
- **WHEN** `activateItem` is called while an activation is already in progress
- **THEN** the second call SHALL return early without registering another observer or triggering another request

---

### Requirement: Button response does not overwrite button content
The "Find Best SMA" button SHALL use `hx-swap="none"` so that the JSON response body is not rendered into the button's innerHTML. The response SHALL be consumed exclusively by the `hx-on::after-request` JavaScript handler.

#### Scenario: Button text preserved during and after request
- **WHEN** the best-sma request completes
- **THEN** the button's label ("Find Best SMA") SHALL remain intact

---

### Requirement: Reload URL uses live form values
When the `after-request` handler constructs the reload URL for `/asset/{symbol}`, it SHALL read `pos`, `sl_short`, and `sl_long` from the current DOM input values at the time of the response, not from server-rendered Jinja2 values baked in at page load time.

#### Scenario: User-edited sl_short reflected in reload
- **WHEN** the user changes the `sl_short` spinner before clicking "Find Best SMA"
- **THEN** the reloaded detail pane SHALL use the user's edited `sl_short` value
