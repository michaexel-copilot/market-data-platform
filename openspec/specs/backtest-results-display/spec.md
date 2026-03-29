# Spec: backtest-results-display

## Purpose

Defines how backtest results (best parameters, train/validation P&L summaries, and validation trade table) are rendered in the strategy-controls accordion after a run completes.

## Requirements

### Requirement: Best parameters displayed prominently
The results section SHALL display the best parameters found (indicator types, winning periods) in a clearly labelled summary row before the P&L stats.

#### Scenario: Best parameters shown after run
- **WHEN** a backtest run completes
- **THEN** the results section SHALL show the winning Indicator 1 type + period (if applicable) and Indicator 2 type + period

---

### Requirement: Training period P&L summary
The results section SHALL display a training-period summary including: date range used, number of trades, net profit/loss in USD, and win rate (%).

#### Scenario: Training summary present in results
- **WHEN** a backtest run completes
- **THEN** the results section SHALL show training date range, trade count, net P&L, and win rate for the training period

---

### Requirement: Validation period P&L summary
The results section SHALL display a validation-period summary including: date range used, number of trades, net profit/loss in USD, and win rate (%).

#### Scenario: Validation summary present in results
- **WHEN** a backtest run completes
- **THEN** the results section SHALL show validation date range, trade count, net P&L, and win rate for the validation period

---

### Requirement: Validation trade table
The results section SHALL display a table listing all trades from the validation period. Each row SHALL include: entry date, entry price, exit date, exit price, P&L (USD), and trade direction (Long/Short).

#### Scenario: Trade table shows all validation trades
- **WHEN** a backtest run completes and validation trades exist
- **THEN** a table with columns Entry Date, Entry Price, Exit Date, Exit Price, P&L, Direction SHALL be displayed under the validation summary

#### Scenario: Empty validation trade table message
- **WHEN** a backtest run completes but the validation period produced zero trades
- **THEN** the trade table area SHALL display the message "No trades in validation period"

---

### Requirement: Results displayed via HTMX swap into dedicated placeholder
The strategy-controls accordion SHALL contain a `<div id="backtest-results">` placeholder. The HTMX POST response SHALL target this element with `hx-swap="innerHTML"`.

#### Scenario: Results injected into placeholder
- **WHEN** the HTMX POST response is received
- **THEN** the `#backtest-results` div SHALL be populated with the results HTML fragment

---

### Requirement: Loading state shown during backtest run
While the backtest POST is in flight, the "Run Backtest" button SHALL show a spinner and be disabled. After the response is received, the button SHALL return to its normal state.

#### Scenario: Button disabled while running
- **WHEN** the "Run Backtest" button is clicked and the HTMX request is pending
- **THEN** the button SHALL display a spinner and SHALL be disabled

#### Scenario: Button re-enabled after response
- **WHEN** the HTMX response is received (success or error)
- **THEN** the "Run Backtest" button SHALL be re-enabled and the spinner removed
