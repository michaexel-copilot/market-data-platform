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

The winning (sma_low, sma_high) pair is the one with the highest combined score. If the total number of closed trades across both strategies is zero for a given pair, that pair's score SHALL be treated as negative infinity.

#### Scenario: Grid covers range 3–50 inclusive
- **WHEN** the best-sma search is run for any symbol
- **THEN** all integer combinations (sma_low, sma_high) with sma_low ∈ [3,50] and sma_high ∈ [3,50] SHALL be evaluated

#### Scenario: Score computed from closed trades only
- **WHEN** a (sma_low, sma_high) pair is scored
- **THEN** only trades where `is_open == False` and `pnl is not None` SHALL contribute to the average

#### Scenario: Winning pair returned in JSON
- **WHEN** the search completes
- **THEN** the endpoint SHALL return a JSON response `{"sma": <int>, "sma_high": <int>}` with the winning values

---

### Requirement: Search result cached in-process
The endpoint SHALL maintain an in-process dict keyed by `(symbol_upper, date.today())`. If a cached result exists for the current day, it SHALL be returned immediately without re-running the search.

#### Scenario: Cache hit on second click
- **WHEN** the best-sma endpoint is called a second time for the same symbol on the same calendar day
- **THEN** the result SHALL be returned from cache without repeating the grid search

#### Scenario: Cache miss forces search
- **WHEN** no cached result exists for (symbol, today)
- **THEN** the full grid search SHALL run

---

### Requirement: Spinner values updated after search
The HTMX response from `/asset/{symbol}/best-sma` SHALL cause the main `#detail-pane` to reload with the winning `sma` and `sma_high` values applied, so both spinners and the chart reflect the optimized pair.

#### Scenario: Detail pane reloads with optimized SMA values
- **WHEN** the best-sma response is received
- **THEN** the `#detail-pane` SHALL reload at `/asset/{symbol}` with `sma=<winning_low>&sma_high=<winning_high>` (plus all other current parameters preserved)
