# Management Console

## Purpose

Defines the browser-based single-page management UI for operating the market data platform — browsing instruments by asset class, inspecting fundamental data, and dispatching data-update actions.

## Requirements

### Requirement: Asset-class selector
The console SHALL display a segmented button bar at the top of the page listing all supported asset classes: `crypto`, `equity`, `etf`, `fx`, `commodity`. The `crypto` class SHALL be selected by default on page load. Selecting a different class SHALL reload the instrument list pane with instruments of that class.

#### Scenario: Default class on load
- **WHEN** the console is opened in a browser
- **THEN** the `crypto` segment is active and the instrument list shows active crypto instruments

#### Scenario: Switching asset class
- **WHEN** the user clicks the `equity` segment button
- **THEN** the instrument list pane is refreshed with active equity instruments and `equity` appears selected

---

### Requirement: Data-source filter button bar
The console SHALL display a second segmented button bar (`SEG_SOURCE_FILTER`) immediately below
`SEG_ASSET_CLASS`. The bar SHALL contain one toggle button per known data source, initially:
**eodhd** (active by default), **hl** (active by default), **yahoo-finance** (inactive by
default), **cmc** (inactive by default). Each button SHALL act as a toggle: clicking an active
button deactivates it; clicking an inactive button activates it. At least one button SHALL
remain active at all times — clicking the last active button SHALL have no effect. The button
bar SHALL be visible at all times regardless of selected asset class.

#### Scenario: Default state on page load
- **WHEN** the console is opened in a browser
- **THEN** `SEG_SOURCE_FILTER` shows four buttons; `eodhd` and `hl` are visually active;
  `yahoo-finance` and `cmc` are inactive; the instrument list is filtered to the intersection
  of `eodhd` and `hl`

#### Scenario: Toggle a source off
- **WHEN** the user clicks the active `hl` button in `SEG_SOURCE_FILTER`
- **THEN** `hl` becomes inactive; the instrument list reloads showing only instruments with
  `source_short_name = 'eodhd'`

#### Scenario: Toggle a source on
- **WHEN** the user clicks the inactive `cmc` button in `SEG_SOURCE_FILTER`
- **THEN** `cmc` becomes active; the instrument list reloads showing the intersection of all
  currently active sources including `cmc`

#### Scenario: Cannot deactivate last source
- **WHEN** only one button in `SEG_SOURCE_FILTER` is active and the user clicks it
- **THEN** the button remains active; the instrument list does not change

#### Scenario: Source filter resets on asset class change
- **WHEN** the user switches asset class via `SEG_ASSET_CLASS`
- **THEN** the active sources in `SEG_SOURCE_FILTER` are preserved; the instrument list reloads
  with both the new asset class and the current active sources applied

---

### Requirement: Instrument list pane
The console SHALL display a scrollable list of instruments in the left pane, filtered by the currently selected asset class **and the currently active data sources in `SEG_SOURCE_FILTER`**. Each list item SHALL show the instrument's `ticker` and `full_name`. Clicking an item SHALL load that instrument's fundamentals in the main pane. The pane SHALL also contain a text input (`INP_INSTRUMENT_FILTER`) above the list that filters the displayed rows live as the user types, matching against `ticker` and `full_name` case-insensitively.

#### Scenario: Instrument list populated
- **WHEN** the instrument list pane is loaded for a given asset class and set of active sources
- **THEN** the pane shows one row per active instrument matching both the asset class and source
  intersection filters

#### Scenario: Instrument selected
- **WHEN** the user clicks an instrument row
- **THEN** the row is highlighted and the fundamentals pane updates with that instrument's data

#### Scenario: Empty asset class
- **WHEN** no active instruments exist for the selected asset class and active sources
- **THEN** the pane shows a "No instruments found" message

#### Scenario: Filter narrows list
- **WHEN** the user types into `INP_INSTRUMENT_FILTER`
- **THEN** only rows whose `ticker` or `full_name` contain the typed string (case-insensitive) are visible; non-matching rows are hidden

#### Scenario: Filter cleared restores full list
- **WHEN** the user clears `INP_INSTRUMENT_FILTER`
- **THEN** all loaded instruments for the current asset class and active sources are shown again

#### Scenario: Filter resets on asset class change
- **WHEN** the user switches asset class via `SEG_ASSET_CLASS`
- **THEN** `INP_INSTRUMENT_FILTER` is cleared and the full list for the new class and active
  sources is shown

#### Scenario: Empty intersection warning
- **WHEN** the instrument list loads with active sources but `instrument_source_intersection`
  returns zero results for those sources
- **THEN** the pane shows "No instruments found. Run import-source-intersection to populate
  source data." instead of a blank list

---

### Requirement: Fundamentals detail pane
The console SHALL display fundamental data for the selected instrument in the main pane. The data SHALL be fetched from `GET /v1/instruments/{symbol}/fundamentals`. Fields SHALL be rendered as a labelled key-value list. If no instrument is selected, the pane SHALL show a placeholder message. Additionally, after a successful migration (`BTN_MIGRATE_FUNDAMENTALS`), the pane SHALL show "Migration complete — N instruments promoted."

The key-value table SHALL include a **Launch Date** row when the API response contains a non-null `launch_date` field. The value SHALL be displayed as `YYYY-MM-DD`. If `launch_date` is null or absent, the row SHALL be omitted entirely.

Below the fundamentals key-value table, the pane SHALL render two additional sections:

**OHLCV Time Range** — a table populated from `GET /v1/instruments/{id}/ohlcv-availability`.
The table SHALL include the columns **Interval / First / Last / Actions**.
For native intervals (`1m`, `5m`, `1h`, `1d`), the `Actions` cell SHALL contain:
- an **Update** button that calls `POST /v1/instruments/{id}/update-ohlcv/{interval}`;
- an **Auto** checkbox that calls `PUT /v1/instruments/{id}/ohlcv-update-settings/{interval}`.

The Update button SHALL be hidden when that interval's persisted `auto_update` flag is true.
The Update button SHALL be disabled when the interval is not stale yet, using these UTC freshness thresholds:
- `1m` → newer than 1 minute
- `5m` → newer than 5 minutes
- `1h` → newer than 1 hour
- `1d` → same UTC day

The `1m` row SHALL always be present even when no `1m` candles have been ingested yet; its `first` and `last` values SHALL display as `—`, and the Update button SHALL remain enabled.
After a successful row-level update or auto-toggle change, the OHLCV sections SHALL be refreshed.

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
- **THEN** the fundamentals pane shows an "OHLCV Time Range" table with columns `Interval`, `First`, `Last`, and `Actions`

#### Scenario: `1m` row shown without data
- **WHEN** the selected instrument has no `1m` rows in `ohlcv`
- **THEN** the OHLCV Time Range table still shows a `1m` row with `First = —`, `Last = —`, and an enabled Update button

#### Scenario: Row-level update available for stale interval
- **WHEN** the selected instrument has stale `1h` data and `auto_update = false`
- **THEN** the `1h` row shows an enabled Update button and an unchecked Auto checkbox

#### Scenario: Row-level update hidden when auto is enabled
- **WHEN** the persisted setting for the `5m` interval is `auto_update = true`
- **THEN** the `5m` row hides the Update button and shows the Auto checkbox as checked

#### Scenario: Row-level update refreshes OHLCV sections
- **WHEN** the user clicks the row-level Update button and the backend returns HTTP 200
- **THEN** an inline success message is shown and the OHLCV Time Range and Data Available sections are refreshed

#### Scenario: Row-level update failure shown inline
- **WHEN** the row-level update request returns a non-200 response or throws a network error
- **THEN** the fundamentals pane shows `"<interval> update failed: <error>"`

#### Scenario: Auto toggle persists setting
- **WHEN** the user checks or unchecks the Auto checkbox for a native interval row
- **THEN** the console sends `PUT /v1/instruments/{id}/ohlcv-update-settings/{interval}` with `{ "auto_update": true|false }` and refreshes the OHLCV sections on success

#### Scenario: OHLCV availability matrix shown
- **WHEN** the user selects an instrument
- **THEN** the "OHLCV Data Available" matrix shows a row per interval and a column per data source with ✓ where `has_<interval>=true`

---

### Requirement: Action button bar
The console SHALL render an action button bar above the fundamentals pane. The bar SHALL
contain the following named elements:

| Element ID | Type | Label |
|---|---|---|
| `BTN_UPDATE_FUNDAMENTALS` | Button | "Update Fundamental Data" |
| `BTN_UPDATE_OHLCV` | Button | "Update OHLCV Data" |

`DDL_OHLCV_PERIOD`, `INP_BEST_SMA_POS_USD`, and `BTN_COMPUTE_BEST_SMA_V2` SHALL NOT be present in the action bar or DOM. `BTN_UPDATE_FUNDAMENTALS` SHALL be disabled when no
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

---

### Requirement: Action button list
The console top bar SHALL contain a right-aligned action button list (`ACT_BTN_LIST`) as a sibling of `#SEG_ASSET_CLASS`. The list SHALL contain a button with id `BTN_MIGRATE_FUNDAMENTALS` and label "Migrate Fundamental Data". The button SHALL be always enabled (not gated on instrument selection).

#### Scenario: Action button list rendered
- **WHEN** the console page loads
- **THEN** `#ACT_BTN_LIST` is visible in the top bar, right-aligned, containing `#BTN_MIGRATE_FUNDAMENTALS`

#### Scenario: Migrate button visible on load
- **WHEN** the console page loads
- **THEN** `#BTN_MIGRATE_FUNDAMENTALS` is enabled regardless of whether an instrument is selected

---

### Requirement: Migrate Fundamental Data action
When `BTN_MIGRATE_FUNDAMENTALS` is clicked, the console SHALL call `POST /v1/admin/migrate-fundamentals`. On success (HTTP 200) the console SHALL reload the instrument list for the currently selected asset class. On failure, the console SHALL display an error message in the fundamentals pane.

#### Scenario: Successful migration triggers list reload
- **WHEN** the user clicks `BTN_MIGRATE_FUNDAMENTALS` and the endpoint returns HTTP 200
- **THEN** the instrument list pane is refreshed with the current asset class and the fundamentals pane shows a success message

#### Scenario: Migration error displayed
- **WHEN** `POST /v1/admin/migrate-fundamentals` returns a non-200 response
- **THEN** the fundamentals pane shows an error message containing the HTTP status code

---

### Requirement: Console served by FastAPI
The system SHALL expose a `GET /console` route in the FastAPI application that returns the management console HTML page. The route SHALL be implemented in `src/market_data/api/rest/console.py` and mounted in `app.py`.

#### Scenario: Console route accessible
- **WHEN** `GET /console` is requested
- **THEN** HTTP 200 is returned with `Content-Type: text/html` and the console page

---

### Requirement: Console element reference documentation
The system SHALL include a documentation file at `docs/management-console.md` describing the console layout, listing all named UI elements with their IDs, types, and purpose, so that operators can refer to them by ID in future refinement requests.

#### Scenario: Documentation lists all named elements
- **WHEN** `docs/management-console.md` is read
- **THEN** it contains a table of all elements with columns: Element ID, Type, Description, Location in UI

---

### Requirement: Auto-select Bitcoin on startup
On page load, after the crypto instrument list is fully rendered, the console SHALL automatically select the first instrument whose `ticker` value equals `BTC` (case-insensitive). This SHALL trigger the same `selectInstrument` flow as a manual click: highlight the row, enable the action bar, and load fundamentals. If no instrument with `ticker = "BTC"` is found in the list, no auto-selection occurs and the page remains in the default unselected state.

#### Scenario: Bitcoin present in list
- **WHEN** the console loads and the crypto instrument list contains an instrument with `ticker = "BTC"`
- **THEN** that instrument is automatically selected, its row is highlighted, the action bar is enabled, and its fundamentals are loaded

#### Scenario: BTC absent from list
- **WHEN** the console loads and no instrument with `ticker = "BTC"` exists in the crypto list
- **THEN** no auto-selection occurs; the page shows the placeholder message "Select an instrument to view details"

---

### Requirement: Scheduler nav button
The console SHALL display a `BTN_NAV_SCHEDULER` button (labelled "⚙ Scheduler") in the top bar alongside the asset-class segment buttons. Clicking it SHALL hide the instrument list pane and the content pane and show the `#PANE_SCHEDULER` div. Clicking any asset-class button while `#PANE_SCHEDULER` is visible SHALL hide `#PANE_SCHEDULER` and restore the normal two-pane layout.

#### Scenario: Navigate to scheduler panel
- **WHEN** the user clicks `BTN_NAV_SCHEDULER`
- **THEN** the instrument list pane and content pane are hidden; `#PANE_SCHEDULER` is visible and populated with the jobs table

#### Scenario: Return to instruments view
- **WHEN** `#PANE_SCHEDULER` is visible and the user clicks an asset-class button
- **THEN** `#PANE_SCHEDULER` is hidden; the instrument list pane and content pane are restored

---

### Requirement: Scheduler jobs table in console
The `#PANE_SCHEDULER` panel SHALL display a table with one row per scheduler job. Each row SHALL show: `job_id`, trigger description, `enabled` status, `next_run_time` (formatted as `YYYY-MM-DD HH:MM UTC` or `—` if null), and an action button labelled "Disable" when the job is enabled or "Enable" when it is disabled.

#### Scenario: Jobs table rendered
- **WHEN** the user navigates to `#PANE_SCHEDULER`
- **THEN** the table shows four rows, one for each known job, with correct `enabled` status and `next_run_time`

#### Scenario: Disabled job row
- **WHEN** a job has `enabled: false`
- **THEN** its row shows `enabled: false`, `next_run_time: —`, and an "Enable" action button

---

### Requirement: Toggle job from console
Clicking the action button in a job row SHALL call the corresponding REST endpoint (`/enable` or `/disable`). During the request the button SHALL be disabled and its label changed to "…". On success the jobs table SHALL be reloaded and re-rendered. On failure an inline error message SHALL appear inside `#PANE_SCHEDULER`.

#### Scenario: Disable a job from the console
- **WHEN** the user clicks "Disable" on an enabled job row
- **THEN** the button is disabled with label "…" during the request; on success the row updates to show `enabled: false` and an "Enable" button

#### Scenario: Enable a job from the console
- **WHEN** the user clicks "Enable" on a disabled job row
- **THEN** on success the row updates to show `enabled: true` and a "Disable" button; `next_run_time` becomes non-null

#### Scenario: Toggle fails
- **WHEN** the toggle REST call returns a non-2xx response
- **THEN** an inline error message is shown in `#PANE_SCHEDULER`; the action button is restored to its original label
