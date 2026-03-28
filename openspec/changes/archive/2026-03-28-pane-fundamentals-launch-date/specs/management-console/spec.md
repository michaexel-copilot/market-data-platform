## MODIFIED Requirements

### Requirement: Fundamentals detail pane
The console SHALL display fundamental data for the selected instrument in the main pane. The data SHALL be fetched from `GET /v1/instruments/{symbol}/fundamentals`. Fields SHALL be rendered as a labelled key-value list. If no instrument is selected, the pane SHALL show a placeholder message. Additionally, after a successful migration (`BTN_MIGRATE_FUNDAMENTALS`), the pane SHALL show "Migration complete — N instruments promoted."

The key-value table SHALL include a **Launch Date** row when the API response contains a non-null `launch_date` field. The value SHALL be displayed as `YYYY-MM-DD`. If `launch_date` is null or absent, the row SHALL be omitted entirely.

Below the fundamentals key-value table, the pane SHALL render two additional sections:

**OHLCV Time Range** — a table with columns Interval / First / Last, populated from `GET /v1/instruments/{id}/ohlcv-availability`. If no OHLCV data exists, the section shows "No OHLCV data available."

**OHLCV Data Available** — a matrix table with rows per interval (1m/5m/1h/1d) and columns per data source showing ✓ or — per cell, populated from `GET /v1/instruments/{id}/ohlcv-data-available`.

#### Scenario: Fundamentals displayed on selection
- **WHEN** the user clicks an instrument row in the list
- **THEN** the main pane renders all non-null fundamental fields returned by the API as label-value pairs

#### Scenario: Launch date shown
- **WHEN** the selected instrument's fundamentals response includes a non-null `launch_date`
- **THEN** the key-value table contains a row with label "Launch Date" and value formatted as `YYYY-MM-DD`

#### Scenario: Launch date absent
- **WHEN** the selected instrument's fundamentals response has `launch_date` as null or missing
- **THEN** no "Launch Date" row appears in the key-value table

#### Scenario: No instrument selected
- **WHEN** the page loads and no instrument has been clicked
- **THEN** the main pane shows "Select an instrument to view details"

#### Scenario: Fundamentals fetch error
- **WHEN** the API returns a non-200 response for the fundamentals request
- **THEN** the main pane shows an error message with the HTTP status code

#### Scenario: Migration success message
- **WHEN** `POST /v1/admin/migrate-fundamentals` returns HTTP 200 with `{promoted: N}`
- **THEN** the fundamentals pane briefly shows "Migration complete — N instruments promoted." before reverting to the placeholder

#### Scenario: OHLCV time range shown
- **WHEN** the user selects an instrument that has OHLCV data
- **THEN** the fundamentals pane shows an "OHLCV Time Range" section with one row per available interval and its first/last timestamps

#### Scenario: No OHLCV data
- **WHEN** the user selects an instrument with no OHLCV rows
- **THEN** the "OHLCV Time Range" section shows "No OHLCV data available"

#### Scenario: OHLCV availability matrix shown
- **WHEN** the user selects an instrument
- **THEN** the "OHLCV Data Available" matrix shows a row per interval and a column per data source with ✓ where `has_<interval>=true`
