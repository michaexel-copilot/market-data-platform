## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Fundamentals detail pane
The console SHALL display fundamental data for the selected instrument in the main pane. The data SHALL be fetched from `GET /v1/instruments/{symbol}/fundamentals`. Fields SHALL be rendered as a labelled key-value list. If no instrument is selected, the pane SHALL show a placeholder message. Additionally, after a successful migration (`BTN_MIGRATE_FUNDAMENTALS`), the pane SHALL show "Migration complete — N instruments promoted."

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
