## ADDED Requirements

### Requirement: Validation trades table is collapsible

The validation trades section in `backtest_results.html` SHALL be wrapped in a Bootstrap collapse so that it is hidden by default when results are rendered. A toggle button SHALL be present to expand and collapse the table.

#### Scenario: Trades hidden on initial render

WHEN a backtest result is displayed
THEN the validation trades table SHALL be collapsed (not visible) by default

#### Scenario: Toggle expands trades

WHEN the user clicks the trades toggle button
THEN the validation trades table SHALL become visible

#### Scenario: Toggle collapses trades again

WHEN the trades table is visible and the user clicks the toggle button again
THEN the validation trades table SHALL be hidden
