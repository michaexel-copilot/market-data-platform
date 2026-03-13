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

### Requirement: Instrument list pane
The console SHALL display a scrollable list of instruments in the left pane, filtered by the currently selected asset class. Each list item SHALL show the instrument's `ticker` and `full_name`. Clicking an item SHALL load that instrument's fundamentals in the main pane. The pane SHALL also contain a text input (`INP_INSTRUMENT_FILTER`) above the list that filters the displayed rows live as the user types, matching against `ticker` and `full_name` case-insensitively.

#### Scenario: Instrument list populated
- **WHEN** the instrument list pane is loaded for a given asset class
- **THEN** the pane shows one row per active instrument with ticker and full name

#### Scenario: Instrument selected
- **WHEN** the user clicks an instrument row
- **THEN** the row is highlighted and the fundamentals pane updates with that instrument's data

#### Scenario: Empty asset class
- **WHEN** no active instruments exist for the selected asset class
- **THEN** the pane shows a "No instruments found" message

#### Scenario: Filter narrows list
- **WHEN** the user types into `INP_INSTRUMENT_FILTER`
- **THEN** only rows whose `ticker` or `full_name` contain the typed string (case-insensitive) are visible; non-matching rows are hidden

#### Scenario: Filter cleared restores full list
- **WHEN** the user clears `INP_INSTRUMENT_FILTER`
- **THEN** all loaded instruments for the current asset class are shown again

#### Scenario: Filter resets on asset class change
- **WHEN** the user switches asset class via `SEG_ASSET_CLASS`
- **THEN** `INP_INSTRUMENT_FILTER` is cleared and the full list for the new class is shown

---

### Requirement: Fundamentals detail pane
The console SHALL display fundamental data for the selected instrument in the main pane. The data SHALL be fetched from `GET /v1/instruments/{symbol}/fundamentals`. Fields SHALL be rendered as a labelled key-value list. If no instrument is selected, the pane SHALL show a placeholder message. Additionally, after a successful migration (`BTN_MIGRATE_FUNDAMENTALS`), the pane SHALL show "Migration complete — N instruments promoted."

Below the fundamentals key-value table, the pane SHALL render two additional sections:

**OHLCV Time Range** — a table with columns Interval / First / Last, populated from `GET /v1/instruments/{id}/ohlcv-availability`. If no OHLCV data exists, the section shows "No OHLCV data available."

**OHLCV Data Available** — a matrix table with rows per interval (1m/5m/1h/1d) and columns per data source showing ✓ or — per cell, populated from `GET /v1/instruments/{id}/ohlcv-data-available`.

#### Scenario: Fundamentals displayed on selection
- **WHEN** the user clicks an instrument row in the list
- **THEN** the main pane renders all non-null fundamental fields returned by the API as label-value pairs

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
The console SHALL render an action button bar above the fundamentals pane. The bar SHALL contain the following named elements:

| Element ID | Type | Label |
|---|---|---|
| `BTN_UPDATE_FUNDAMENTALS` | Button | "Update Fundamental Data" |
| `BTN_UPDATE_OHLCV` | Button | "Update OHLCV Data" |
| `DDL_OHLCV_PERIOD` | Dropdown (select) | Period selector: `1m`, `5m`, `1h`, `1d`, `1w`, `1mo`, `1y` |

`DDL_OHLCV_PERIOD` SHALL be positioned immediately adjacent to `BTN_UPDATE_OHLCV`. `BTN_UPDATE_FUNDAMENTALS` SHALL be disabled when no instrument is selected. `BTN_UPDATE_OHLCV` and `DDL_OHLCV_PERIOD` SHALL be disabled when no instrument is selected.

When `BTN_UPDATE_OHLCV` is clicked with an instrument selected, the console SHALL call `POST /v1/admin/import-ohlcv-cache` with `{instrument_id, interval}` (where `interval` is the current value of `DDL_OHLCV_PERIOD`). `BTN_UPDATE_OHLCV` SHALL show a disabled loading state ("Importing…") during the request.

On a successful import (`status = "ok"`), the console SHALL display an inline message in the fundamentals pane: "Imported N rows from cache." and refresh the OHLCV availability sections.

On `status = "folder_not_found"`, the console SHALL display an inline error in the fundamentals pane: "Cache folder not found. Expected: <expected_path>". The fundamentals content SHALL remain unchanged.

On any other HTTP or network error, the console SHALL display: "OHLCV import failed: <error message>".

After the request completes (success or error), `BTN_UPDATE_OHLCV` SHALL return to its enabled, normal state.

#### Scenario: Buttons disabled on load
- **WHEN** the page loads with no instrument selected
- **THEN** both action buttons and the period dropdown are disabled

#### Scenario: Buttons enabled on selection
- **WHEN** an instrument is selected
- **THEN** `BTN_UPDATE_FUNDAMENTALS`, `BTN_UPDATE_OHLCV`, and `DDL_OHLCV_PERIOD` become enabled

#### Scenario: BTN_UPDATE_FUNDAMENTALS click stub
- **WHEN** `BTN_UPDATE_FUNDAMENTALS` is clicked
- **THEN** a browser console message is logged: `[stub] BTN_UPDATE_FUNDAMENTALS clicked for <instrument_id>`

#### Scenario: BTN_UPDATE_OHLCV starts import
- **WHEN** `BTN_UPDATE_OHLCV` is clicked with an instrument selected
- **THEN** the button shows "Importing…" and is disabled while the backend request is in flight

#### Scenario: BTN_UPDATE_OHLCV import success
- **WHEN** `POST /v1/admin/import-ohlcv-cache` returns `{status: "ok", rows_imported: 42}`
- **THEN** an inline message "Imported 42 rows from cache." is shown and OHLCV sections are refreshed

#### Scenario: BTN_UPDATE_OHLCV folder not found
- **WHEN** the response contains `{status: "folder_not_found", expected_path: "/appdata/eodhd/intraday_historical_data/1-hour"}`
- **THEN** an error message "Cache folder not found. Expected: /appdata/eodhd/intraday_historical_data/1-hour" is displayed

#### Scenario: BTN_UPDATE_OHLCV network error
- **WHEN** the fetch call throws or the server returns a non-200 status
- **THEN** "OHLCV import failed: <error>" is shown in the fundamentals pane

#### Scenario: BTN_UPDATE_OHLCV button re-enabled after request
- **WHEN** the backend request completes (any outcome)
- **THEN** `BTN_UPDATE_OHLCV` returns to its enabled state with original label "Update OHLCV Data"

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
