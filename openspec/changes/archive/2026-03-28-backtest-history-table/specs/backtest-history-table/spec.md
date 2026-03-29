## ADDED Requirements

### Requirement: Backtest history endpoint

The system SHALL expose `GET /asset/{symbol}/backtest-history` that returns an HTML partial (`backtest_history.html`) listing all cached backtest runs for the given symbol.

#### Scenario: Cached runs exist

WHEN `GET /asset/BTC/backtest-history` is called and cached results exist
THEN it SHALL return a rendered HTML table with one row per cached run

#### Scenario: No cached runs

WHEN `GET /asset/BTC/backtest-history` is called and no cached results exist
THEN it SHALL return an empty-state HTML message

### Requirement: History table columns

The history table SHALL include the following columns per row: Train Start, Train End, Val Start, Indicator 1 (type + best period), Indicator 2 (type + best period), Exposure, Train Net P&L ($), Val Net P&L ($), Val Trades, and a "Load" button.

#### Scenario: Row displays best params not range

WHEN a result row is rendered
THEN the Indicator columns SHALL show the best parameter found (e.g. "SMA-63"), not the search range

#### Scenario: Load button populates form

WHEN the user clicks the "Load" button on a history row
THEN the backtest form fields (`ind1_type`, `ind1_min`, `ind1_max`, `ind2_type`, `ind2_min`, `ind2_max`, `exposure`, `train_start`, `train_end`, `val_start`) SHALL be populated with the stored `_params` values without triggering a new backtest run

### Requirement: History refreshes after new backtest

The history table SHALL reload automatically after a successful backtest POST request completes.

#### Scenario: New backtest run triggers history refresh

WHEN a POST to `/asset/{symbol}/backtest` returns successfully
THEN `#backtest-history` SHALL be refreshed by issuing a new GET to `/asset/{symbol}/backtest-history`

### Requirement: History loads on accordion open

The history section SHALL be loaded via HTMX when the strategy-controls accordion is first expanded.

#### Scenario: First accordion open triggers load

WHEN the `#collapse-strategy-controls` accordion is opened for the first time
THEN `#backtest-history` SHALL be populated by a GET to `/asset/{symbol}/backtest-history`
