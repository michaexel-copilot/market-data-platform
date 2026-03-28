## MODIFIED Requirements

### Requirement: Fundamentals detail pane
The console SHALL display fundamental data for the selected instrument in the main pane. The data SHALL be fetched from `GET /v1/instruments/{symbol}/fundamentals`. Fields SHALL be rendered as a labelled key-value list. If no instrument is selected, the pane SHALL show a placeholder message. Additionally, after a successful migration (`BTN_MIGRATE_FUNDAMENTALS`), the pane SHALL show "Migration complete — N instruments promoted."

The key-value table SHALL include a **Launch Date** row when the API response contains a non-null `launch_date` field. The value SHALL be displayed as `YYYY-MM-DD`. If `launch_date` is null or absent, the row SHALL be omitted entirely.

Below the fundamentals key-value table, the pane SHALL render two additional sections:

**OHLCV Time Range** — a table with columns Interval / First / Last, populated from `GET /v1/instruments/{id}/ohlcv-availability`. If no OHLCV data exists, the section shows "No OHLCV data available."

**OHLCV Data Available** — a matrix table with rows per interval (1m/5m/1h/1d) and columns per data source showing ✓ or — per cell, populated from `GET /v1/instruments/{id}/ohlcv-data-available`.

No other sections SHALL be rendered in the fundamentals pane. In particular, a "Best SMA Exit V1" section (`best-sma-v2-section`) SHALL NOT be present.

#### Scenario: Fundamentals displayed on selection
- **WHEN** the user clicks an instrument row in the list
- **THEN** the main pane renders all non-null fundamental fields returned by the API as label-value pairs

#### Scenario: Launch date shown
- **WHEN** the selected instrument's fundamentals response includes a non-null `launch_date`
- **THEN** the key-value table contains a row with label "Launch Date" and value formatted as `YYYY-MM-DD`

#### Scenario: Launch date absent
- **WHEN** the selected instrument's fundamentals response has `launch_date` as null or missing
- **THEN** no "Launch Date" row appears in the key-value table

#### Scenario: No Best SMA section rendered
- **WHEN** the user selects any instrument
- **THEN** no element with class `best-sma-v2-section` or heading "BEST SMA Exit V1" appears in the fundamentals pane

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

---

### Requirement: Action button bar
The console SHALL render an action button bar above the fundamentals pane. The bar SHALL
contain the following named elements, and no others:

| Element ID | Type | Label |
|---|---|---|
| `BTN_UPDATE_FUNDAMENTALS` | Button | "Update Fundamental Data" |
| `BTN_UPDATE_OHLCV` | Button | "Update OHLCV Data" |

`DDL_OHLCV_PERIOD`, `INP_BEST_SMA_POS_USD`, and `BTN_COMPUTE_BEST_SMA_V2` SHALL NOT be present in the action bar or DOM. `BTN_UPDATE_FUNDAMENTALS` SHALL be disabled when no instrument is selected. `BTN_UPDATE_OHLCV` SHALL be disabled when no instrument is selected.

When `BTN_UPDATE_OHLCV` is clicked with an instrument selected, the console SHALL call
`POST /v1/admin/smart-update-ohlcv` with `{ "instrument_id": "<selected id>" }`. The button
SHALL show a disabled loading state ("Updating…") during the request.

On a successful response (HTTP 200), the console SHALL display an inline summary message in
the fundamentals pane derived from the `steps` array:
- If the `1h_freshness_check` step is present, the message SHALL include the freshness
  outcome (stale/fresh) and the `last_ts` value.
- If the `1h_ingest` step has `status = "ok"`, the message SHALL include the number of rows
  written.
- If the `1m_fetch` step has `status = "ok"`, the message SHALL include the number of
  candles fetched.
- If the `1h_aggregation` step has `status = "ok"`, the message SHALL include the number of
  synthetic 1h candles written.
- If the `binance_availability` step has `status = "unavailable"`, the message SHALL note
  that gap fill was skipped.

The OHLCV availability sections SHALL be refreshed after a successful response.

On any HTTP or network error, the console SHALL display: "OHLCV update failed: <error>".

After the request completes (success or error), `BTN_UPDATE_OHLCV` SHALL return to its
enabled, normal state with the label "Update OHLCV Data".

#### Scenario: Buttons disabled on load
- **WHEN** the page loads with no instrument selected
- **THEN** both action buttons are disabled

#### Scenario: Buttons enabled on selection
- **WHEN** an instrument is selected
- **THEN** `BTN_UPDATE_FUNDAMENTALS` and `BTN_UPDATE_OHLCV` become enabled

#### Scenario: No period dropdown present
- **WHEN** the console page is rendered
- **THEN** no `DDL_OHLCV_PERIOD` element exists in the DOM

#### Scenario: No Best SMA controls present
- **WHEN** the console page is rendered
- **THEN** no `INP_BEST_SMA_POS_USD` or `BTN_COMPUTE_BEST_SMA_V2` element exists in the DOM

#### Scenario: BTN_UPDATE_OHLCV shows loading state
- **WHEN** `BTN_UPDATE_OHLCV` is clicked with an instrument selected
- **THEN** the button shows "Updating…" and is disabled while the backend request is in flight

#### Scenario: BTN_UPDATE_OHLCV smart update success — stale with Binance fill
- **WHEN** `POST /v1/admin/smart-update-ohlcv` returns steps indicating stale 1h data, 1h ingest of 12 rows, and 4 synthetic 1h candles aggregated from 240 Binance 1m candles
- **THEN** an inline summary message is shown containing the written counts and OHLCV sections are refreshed

#### Scenario: BTN_UPDATE_OHLCV smart update — fresh, no gap
- **WHEN** `POST /v1/admin/smart-update-ohlcv` returns steps indicating fresh 1h data and no 1m gap
- **THEN** an inline message is shown reflecting the fresh status; no error is displayed

#### Scenario: BTN_UPDATE_OHLCV smart update — Binance unavailable
- **WHEN** `POST /v1/admin/smart-update-ohlcv` returns a `binance_availability` step with `status = "unavailable"`
- **THEN** the inline message notes that gap fill was skipped

#### Scenario: BTN_UPDATE_OHLCV network error
- **WHEN** the fetch call throws or the server returns a non-200 status
- **THEN** "OHLCV update failed: <error>" is shown in the fundamentals pane

#### Scenario: BTN_UPDATE_OHLCV button re-enabled after request
- **WHEN** the backend request completes (any outcome)
- **THEN** `BTN_UPDATE_OHLCV` returns to its enabled state with label "Update OHLCV Data"
