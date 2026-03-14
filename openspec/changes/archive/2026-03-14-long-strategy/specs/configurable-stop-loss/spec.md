## ADDED Requirements

### Requirement: Configurable stop loss per strategy
The system SHALL accept separate stop loss values for the short strategy (`sl_short`) and the long strategy (`sl_long`) as integer percentage URL parameters (e.g. `sl_short=10` means 10%). Both SHALL default to 10. Both SHALL be converted to a decimal fraction before being passed to the backtest functions (`stop_loss_pct = sl_short / 100.0`).

#### Scenario: Custom short stop loss
- **WHEN** `sl_short=15` is in the URL
- **THEN** the short strategy uses `stop_loss_pct=0.15`

#### Scenario: Custom long stop loss
- **WHEN** `sl_long=8` is in the URL
- **THEN** the long strategy uses `stop_loss_pct=0.08`

#### Scenario: Default stop loss
- **WHEN** neither `sl_short` nor `sl_long` is in the URL
- **THEN** both strategies use `stop_loss_pct=0.10`

### Requirement: SL Short % spinner
The UI SHALL include a spinner labelled "SL Short %" with default value 10, minimum 1, maximum 50, step 1. It SHALL support the same keyboard shortcuts as the SMA spinners (±1, Shift ±5, Ctrl+Shift ±10). Changing the value SHALL reload the Chart & Trades section via HTMX.

#### Scenario: SL spinner keyboard interaction
- **WHEN** the SL Short % spinner is focused and Shift+`+` is pressed
- **THEN** the value increases by 5 and the section reloads

### Requirement: SL Long % spinner
The UI SHALL include a spinner labelled "SL Long %" with default value 10, minimum 1, maximum 50, step 1 with the same keyboard shortcuts. Changing the value SHALL reload the Chart & Trades section via HTMX.

#### Scenario: SL Long spinner default
- **WHEN** the page loads without `sl_long` in the URL
- **THEN** the SL Long % spinner shows 10
