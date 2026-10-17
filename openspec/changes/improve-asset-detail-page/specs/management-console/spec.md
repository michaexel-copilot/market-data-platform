## MODIFIED Requirements

### Requirement: Fundamentals detail pane
The console SHALL display fundamental data for the selected instrument in the main pane. The data SHALL be fetched from `GET /v1/instruments/{symbol}/fundamentals`. Fields SHALL be rendered as a labelled key-value list. If no instrument is selected, the pane SHALL show a placeholder message. Additionally, after a successful migration (`BTN_MIGRATE_FUNDAMENTALS`), the pane SHALL show "Migration complete — N instruments promoted."

The key-value table SHALL include a **Launch Date** row when the API response contains a non-null `launch_date` field. The value SHALL be displayed as `YYYY-MM-DD`. If `launch_date` is null or absent, the row SHALL be omitted entirely.

Below the fundamentals key-value table, the pane SHALL render the following analysis flow in order:
1. Cached Backtests table
2. Validation Trades section (directly below Cached Backtests)
3. `Performance` accordion item containing the performance chart

The accordion item `Chart & Trades: Chart` SHALL NOT be present.

When a cached backtest is loaded (via the Load button or after a new backtest run that loads cached results), the console SHALL automatically open the `Performance` accordion item.

Inside `Performance`, the chart SHALL overlay price and indicators on a 1-day basis.
The chart time window SHALL be:
- from 5 days before the opened trade through today, when opened-trade context exists; or
- at least the last 30 days through today, when trade context is unavailable.

No other sections SHALL be rendered in the fundamentals pane beyond the capabilities defined by this requirement and other active management-console requirements.

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

#### Scenario: Chart accordion removed
- **WHEN** the asset detail page is rendered
- **THEN** the accordion item `Chart & Trades: Chart` is not present

#### Scenario: Validation trades section repositioned
- **WHEN** cached backtest data is visible
- **THEN** Validation Trades is rendered directly under the Cached Backtests table

#### Scenario: Performance auto-open on cached load
- **WHEN** a cached backtest is loaded by either supported load path
- **THEN** the `Performance` accordion item opens automatically

#### Scenario: Performance chart uses opened-trade context
- **WHEN** an opened-trade timestamp is available for the loaded backtest
- **THEN** the chart range starts 5 days before the opened trade and ends today on daily candles

#### Scenario: Performance chart falls back to 30-day range
- **WHEN** opened-trade context is unavailable
- **THEN** the chart shows at least the last 30 days through today on daily candles
