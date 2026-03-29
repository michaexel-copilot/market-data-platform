# Spec: backtest-param-optimization

## Purpose

Defines how the backend optimises indicator parameters over training data using `backtesting.py`'s `Backtest.optimize()`, selects the best combination by equity final, and validates those parameters on held-out data.

## Requirements

### Requirement: Parameter optimisation runs on training data
When the user clicks "Run Backtest", the backend SHALL slice the OHLCV data to include only rows where `date <= train_end_date` and pass this slice to `Backtest.optimize()`. The optimised metric SHALL be `SQN` (System Quality Number) or `Equity Final [$]` — whichever gives the highest net profit. The winning parameter combination SHALL be the one with the highest `Equity Final [$]`.

#### Scenario: Training data sliced at train_end_date
- **WHEN** an optimisation is triggered with `train_end_date = "2024-12-31"`
- **THEN** only candles with `date <= 2024-12-31` SHALL be passed to `Backtest.optimize()`

#### Scenario: Best parameters selected by highest equity final
- **WHEN** `Backtest.optimize()` completes
- **THEN** the winning combination SHALL be the one with the maximum `Equity Final [$]` among all evaluated combinations

---

### Requirement: Period range supplied by UI inputs
The period ranges for Indicator 1 and Indicator 2 SHALL be passed from the UI form inputs (`ind1_min`, `ind1_max`, `ind2_min`, `ind2_max`) to the backend endpoint. The backend SHALL use these as the `range()` bounds for `Backtest.optimize()`.

#### Scenario: Period ranges forwarded to optimizer
- **WHEN** the user sets Indicator 2 min=5, max=50
- **THEN** `Backtest.optimize(ind2_period=range(5, 51))` SHALL be called

#### Scenario: Indicator 1 period range omitted when Indicator 1 = Price
- **WHEN** `ind1_type` is `price`
- **THEN** the `ind1_period` parameter SHALL NOT be included in the `optimize()` call

---

### Requirement: Optimisation capped at 10 000 combinations
If the product of the two period ranges exceeds 10 000 combinations, the backend SHALL automatically step the ranges to reduce the total below 10 000 (by using `range(min, max+1, step)` where `step = ceil(range_size / 100)`).

#### Scenario: Large range is automatically stepped
- **WHEN** `ind1_period` range is 1–200 and `ind2_period` range is 1–200 (= 40 000 combos)
- **THEN** the backend SHALL compute a step > 1 such that total combinations ≤ 10 000

---

### Requirement: Validation run with best parameters
After finding the best parameters on training data, the backend SHALL construct a second `Backtest` using only rows where `date >= val_start_date` and run it with the winning parameters (no further optimisation).

#### Scenario: Validation data sliced at val_start_date
- **WHEN** validation is run with `val_start_date = "2025-01-01"`
- **THEN** only candles with `date >= 2025-01-01` SHALL be passed to the validation `Backtest`

#### Scenario: Winning parameters used for validation without re-optimising
- **WHEN** the validation Backtest is executed
- **THEN** it SHALL use the best parameters found during optimisation and SHALL NOT call `optimize()` again

---

### Requirement: Backtest endpoint POST /asset/{symbol}/backtest
The system SHALL expose `POST /asset/{symbol}/backtest` accepting form fields: `ind1_type`, `ind2_type`, `ind1_min`, `ind1_max`, `ind2_min`, `ind2_max`, `exposure`, `train_end`, `val_start`. It SHALL return an HTML fragment (for HTMX swap) with the results summary and trade table.

#### Scenario: Endpoint accepts form parameters and returns HTML
- **WHEN** a POST is made to `/asset/BTC/backtest` with valid form fields
- **THEN** the response SHALL be an HTML fragment containing the optimisation results

#### Scenario: Invalid symbol returns 404
- **WHEN** a POST is made to `/asset/FAKECOIN/backtest`
- **THEN** the response SHALL return HTTP 404 or an error HTML fragment
