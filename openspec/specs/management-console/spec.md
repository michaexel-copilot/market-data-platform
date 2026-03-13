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
The console SHALL display a scrollable list of instruments in the left pane, filtered by the currently selected asset class. Each list item SHALL show the instrument's `ticker` and `full_name`. Clicking an item SHALL load that instrument's fundamentals in the main pane.

#### Scenario: Instrument list populated
- **WHEN** the instrument list pane is loaded for a given asset class
- **THEN** the pane shows one row per active instrument with ticker and full name

#### Scenario: Instrument selected
- **WHEN** the user clicks an instrument row
- **THEN** the row is highlighted and the fundamentals pane updates with that instrument's data

#### Scenario: Empty asset class
- **WHEN** no active instruments exist for the selected asset class
- **THEN** the pane shows a "No instruments found" message

---

### Requirement: Fundamentals detail pane
The console SHALL display fundamental data for the selected instrument in the main pane. The data SHALL be fetched from `GET /v1/instruments/{symbol}/fundamentals`. Fields SHALL be rendered as a labelled key-value list. If no instrument is selected, the pane SHALL show a placeholder message.

#### Scenario: Fundamentals displayed on selection
- **WHEN** the user selects an instrument
- **THEN** the main pane renders all available fundamental fields returned by the API as label-value pairs

#### Scenario: No instrument selected
- **WHEN** the page loads and no instrument has been clicked
- **THEN** the main pane shows "Select an instrument to view details"

#### Scenario: Fundamentals fetch error
- **WHEN** the API returns a non-200 response for the fundamentals request
- **THEN** the main pane shows an error message with the HTTP status code

---

### Requirement: Action button bar
The console SHALL render an action button bar above the fundamentals pane. The bar SHALL contain the following named elements — no backend logic is implemented; buttons log a console message only:

| Element ID | Type | Label |
|---|---|---|
| `BTN_UPDATE_FUNDAMENTALS` | Button | "Update Fundamental Data" |
| `BTN_UPDATE_OHLCV` | Button | "Update OHLCV Data" |
| `DDL_OHLCV_PERIOD` | Dropdown (select) | Period selector: `1m`, `5m`, `1h`, `1d`, `1w`, `1mo`, `1y` |

`DDL_OHLCV_PERIOD` SHALL be positioned immediately adjacent to `BTN_UPDATE_OHLCV`. `BTN_UPDATE_FUNDAMENTALS` SHALL be disabled when no instrument is selected. `BTN_UPDATE_OHLCV` and `DDL_OHLCV_PERIOD` SHALL be disabled when no instrument is selected.

#### Scenario: Buttons disabled on load
- **WHEN** the page loads with no instrument selected
- **THEN** both action buttons and the period dropdown are disabled

#### Scenario: Buttons enabled on selection
- **WHEN** an instrument is selected
- **THEN** `BTN_UPDATE_FUNDAMENTALS`, `BTN_UPDATE_OHLCV`, and `DDL_OHLCV_PERIOD` become enabled

#### Scenario: BTN_UPDATE_FUNDAMENTALS click stub
- **WHEN** `BTN_UPDATE_FUNDAMENTALS` is clicked
- **THEN** a browser console message is logged: `[stub] BTN_UPDATE_FUNDAMENTALS clicked for <instrument_id>`

#### Scenario: BTN_UPDATE_OHLCV click stub
- **WHEN** `BTN_UPDATE_OHLCV` is clicked
- **THEN** a browser console message is logged: `[stub] BTN_UPDATE_OHLCV clicked for <instrument_id>, period=<selected DDL_OHLCV_PERIOD value>`

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
