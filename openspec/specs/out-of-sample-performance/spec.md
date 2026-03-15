## ADDED Requirements

### Requirement: Validation backtest runs on held-out candles
After `_find_best_sma` returns the winning `(sma_low, sma_high)` pair using the training slice (first 80 % of candles), the best-sma route handler SHALL run `backtest_short_strategy` and `backtest_long_strategy` on the **remaining 20 % of candles** (validation slice: `candles[split_idx:]`) using the winning SMA values and the same stop-loss/position parameters.

#### Scenario: Validation uses correct candle slice
- **WHEN** the best-sma route handler processes a response
- **THEN** `backtest_short_strategy` and `backtest_long_strategy` SHALL be called with `candles[floor(len(candles) * 0.8):]` and the winning SMA arrays computed from that slice

#### Scenario: Validation summary computed from closed trades
- **WHEN** the validation backtest completes
- **THEN** the short and long summaries SHALL each contain: `count` (closed trades only), `total_pnl` (sum of closed P&L), `avg_pnl` (total_pnl / count, or `None` if count == 0)

---

### Requirement: Training and validation date ranges passed to template
The route handler SHALL compute and pass four date strings to the template context:
- `train_date_from`: date of the first candle in the training slice
- `train_date_to`: date of the last candle in the training slice
- `val_date_from`: date of the first candle in the validation slice
- `val_date_to`: date of the last candle in the validation slice

#### Scenario: Date range matches candle boundaries
- **WHEN** the template receives date-range variables
- **THEN** `train_date_from` SHALL equal `candles[0]["date"]` and `val_date_to` SHALL equal `candles[-1]["date"]`

#### Scenario: Variables absent when best-SMA not yet run
- **WHEN** the detail pane is rendered without a prior "Find Best SMA" call
- **THEN** the template variables `out_of_sample_short_summary`, `out_of_sample_long_summary`, `train_date_from`, etc. SHALL be absent or `None`, and the out-of-sample section SHALL NOT be rendered

---

### Requirement: Out-of-sample summary section displayed in UI
The Chart & Trades accordion SHALL display an **"Out-of-Sample (Validation)"** summary section immediately below the existing in-sample strategy summaries. The in-sample section SHALL be labelled **"In-Sample (Optimisation)"** with its date range. The out-of-sample section SHALL show its own date range and the validation trade count, total P&L, and avg P&L per trade for each strategy.

#### Scenario: In-sample label and date range visible
- **WHEN** the best-SMA result is displayed
- **THEN** the existing summary SHALL carry the label "In-Sample (Optimisation)" and show the training date range (e.g. "2020-01-01 → 2024-04-15")

#### Scenario: Out-of-sample section visible after best-SMA run
- **WHEN** "Find Best SMA" has been clicked and the detail pane rendered
- **THEN** an "Out-of-Sample (Validation)" section SHALL appear with the validation date range, short trade count/P&L, and long trade count/P&L

#### Scenario: Out-of-sample section absent without best-SMA
- **WHEN** the detail pane is loaded with manually set SMA values (no best-SMA call)
- **THEN** the out-of-sample section SHALL NOT be rendered

#### Scenario: Both sections visually separated
- **WHEN** both the in-sample and out-of-sample sections are shown
- **THEN** a visible divider or distinct background/label SHALL separate them so the user can clearly distinguish test (training) data from validation performance
