## MODIFIED Requirements

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
