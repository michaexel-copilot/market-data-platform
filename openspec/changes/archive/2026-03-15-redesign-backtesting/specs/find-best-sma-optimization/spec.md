## MODIFIED Requirements

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

---

## REMOVED Requirements

### Requirement: Search result cached in-process
**Reason**: The 80/20 split makes the result dependent on the daily growing candle set; a same-day cached result from a prior fetch would use a different training boundary. Removal ensures freshness without complexity.
**Migration**: No migration needed — this was an internal optimisation only. Callers (the HTMX route) are unaffected.
