## MODIFIED Requirements

### Requirement: Action button bar
The console SHALL render an action button bar above the fundamentals pane. The bar SHALL
contain the following named elements:

| Element ID | Type | Label |
|---|---|---|
| `BTN_UPDATE_FUNDAMENTALS` | Button | "Update Fundamental Data" |
| `BTN_UPDATE_OHLCV` | Button | "Update OHLCV Data" |

`DDL_OHLCV_PERIOD` is removed. `BTN_UPDATE_FUNDAMENTALS` SHALL be disabled when no
instrument is selected. `BTN_UPDATE_OHLCV` SHALL be disabled when no instrument is selected.

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
