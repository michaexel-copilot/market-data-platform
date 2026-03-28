## ADDED Requirements

### Requirement: Kraken 1h status badge in Fundamentals
The ShortDesk asset detail view SHALL display a compact status card in the
Fundamentals accordion row showing the Kraken 1h data state for the current asset.

The card SHALL show one of three states:
- **No file** (warning): "No file: {PAIR}_60.csv" — orange/yellow badge
- **Gap available** (info): "Gap: {N} rows" — blue badge, with import button clickable
- **Imported** (success): "Kraken 1h ✓" — green badge

The status SHALL be fetched from `GET /v1/instruments/{symbol}/kraken-1h-status`
on each asset detail render (not cached between asset switches).

When the platform API is unreachable or returns an error, the card SHALL be hidden
(no visible error to the user).

#### Scenario: No CSV file exists
- **WHEN** the asset detail page loads and `has_file: false` is returned
- **THEN** a warning badge reading "No file: {PAIR}_60.csv" is displayed in the Fundamentals row

#### Scenario: Gap exists and not yet imported
- **WHEN** `has_file: true`, `already_imported: false`, and `gap_rows > 0`
- **THEN** an info badge reading "Gap: {N} rows" is displayed

#### Scenario: Already imported
- **WHEN** `already_imported: true`
- **THEN** a success badge reading "Kraken 1h ✓" is displayed

#### Scenario: API unavailable
- **WHEN** the platform returns an error or times out
- **THEN** no Kraken status card is shown (silent degradation, no error message to the user)

---

### Requirement: Import Kraken 1h action button
The ShortDesk asset detail view SHALL display an "Import Kraken 1h" button in the
Strategy Controls section, positioned alongside the existing "Find Best SMA" button.

The button SHALL:
- Be disabled/hidden when `has_file: false` or `already_imported: true`
- Be enabled when `has_file: true` and `already_imported: false`
- On click, POST to `/asset/{symbol}/import-kraken-1h` (ShortDesk relay endpoint)
- Show a spinner while the request is in-flight
- On success, reload the Fundamentals section to reflect the new badge state
- On error, display the error message inline near the button

The ShortDesk relay endpoint (`POST /asset/{symbol}/import-kraken-1h`) SHALL forward
the request to `POST /v1/instruments/{symbol}/import-kraken-1h` on the platform and
return the result as JSON.

#### Scenario: Button visible and clicked with gap available
- **WHEN** `gap_rows > 0` and `already_imported: false` and user clicks the button
- **THEN** a spinner is shown on the button
- **THEN** the platform import endpoint is called
- **THEN** on success the Fundamentals badge updates to "Kraken 1h ✓"

#### Scenario: Button hidden when no file
- **WHEN** `has_file: false`
- **THEN** the "Import Kraken 1h" button is not visible

#### Scenario: Button hidden after successful import
- **WHEN** `already_imported: true`
- **THEN** the "Import Kraken 1h" button is not visible

#### Scenario: Import fails
- **WHEN** the platform returns a non-200 response
- **THEN** an inline error message is shown near the button
- **THEN** the button returns to its enabled state
