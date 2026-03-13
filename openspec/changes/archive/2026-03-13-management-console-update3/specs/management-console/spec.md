## MODIFIED Requirements

### Requirement: Fundamentals detail pane
The console SHALL display fundamental data for the selected instrument in the main pane. The data SHALL be fetched from `GET /v1/instruments/{symbol}/fundamentals`. Fields SHALL be rendered as a labelled key-value list. If no instrument is selected, the pane SHALL show a placeholder message. Additionally, after a successful migration (`BTN_MIGRATE_FUNDAMENTALS`), the pane SHALL show "Migration complete — N instruments promoted."

Below the fundamentals key-value table, the pane SHALL render two additional sections:

**OHLCV Time Range** — a table with columns Interval / First / Last, populated from `GET /v1/instruments/{id}/ohlcv-availability`. If no OHLCV data exists, the section shows "No OHLCV data available."

**OHLCV Data Available** — a matrix table with rows per interval (1m/5m/1h/1d) and columns per data source showing ✓ or — per cell, populated from `GET /v1/instruments/{id}/ohlcv-data-available`.

#### Scenario: OHLCV time range shown
- **WHEN** the user selects an instrument that has OHLCV data
- **THEN** the fundamentals pane shows an "OHLCV Time Range" section with one row per available interval and its first/last timestamps

#### Scenario: No OHLCV data
- **WHEN** the user selects an instrument with no OHLCV rows
- **THEN** the "OHLCV Time Range" section shows "No OHLCV data available"

#### Scenario: OHLCV availability matrix shown
- **WHEN** the user selects an instrument
- **THEN** the "OHLCV Data Available" matrix shows a row per interval and a column per data source with ✓ where `has_<interval>=true`
