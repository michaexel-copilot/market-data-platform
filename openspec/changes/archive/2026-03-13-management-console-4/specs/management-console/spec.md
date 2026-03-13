## ADDED Requirements

### Requirement: Auto-select Bitcoin on startup
On page load, after the crypto instrument list is fully rendered, the console SHALL automatically select the first instrument whose `ticker` value equals `BTC` (case-insensitive). This SHALL trigger the same `selectInstrument` flow as a manual click: highlight the row, enable the action bar, and load fundamentals. If no instrument with `ticker = "BTC"` is found in the list, no auto-selection occurs and the page remains in the default unselected state.

#### Scenario: Bitcoin present in list
- **WHEN** the console loads and the crypto instrument list contains an instrument with `ticker = "BTC"`
- **THEN** that instrument is automatically selected, its row is highlighted, the action bar is enabled, and its fundamentals are loaded

#### Scenario: BTC absent from list
- **WHEN** the console loads and no instrument with `ticker = "BTC"` exists in the crypto list
- **THEN** no auto-selection occurs; the page shows the placeholder message "Select an instrument to view details"

---

## MODIFIED Requirements

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
