## MODIFIED Requirements

### Requirement: Load button populates form

WHEN the user clicks the "Load" button on a history row
THEN the backtest form fields (`ind1_type`, `ind2_type`, `ind1_min`, `ind1_max`, `ind2_type`, `ind2_min`, `ind2_max`, `exposure`, `train_start`, `train_end`, `val_start`) SHALL be populated — with `ind1_min`/`ind1_max` set to the best `ind1_period` found, and `ind2_min`/`ind2_max` set to the best `ind2_period` found (not the original search range).

#### Scenario: Indicator range set to best period

- **WHEN** the user clicks "Load" on a history row whose `best_params.ind1_period` is 63 and `best_params.ind2_period` is 21
- **THEN** `#ind1-min` and `#ind1-max` SHALL both be set to 63, and `#ind2-min` and `#ind2-max` SHALL both be set to 21

#### Scenario: Load shows results panel immediately

- **WHEN** the user clicks "Load" on a history row
- **THEN** the `#backtest-results` div SHALL be populated with the cached results HTML (Best Parameters Found summary, train/val stats, validation trades table) without requiring the user to click "Run Backtest"

#### Scenario: Load button carries results URL

- **WHEN** the history table is rendered
- **THEN** each Load button SHALL carry a `data-results-url` attribute containing the full URL to `GET /asset/{symbol}/backtest-cache/file/{filename}/results` for that row's cache file
