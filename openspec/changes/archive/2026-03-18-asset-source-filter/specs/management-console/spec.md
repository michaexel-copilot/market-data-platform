## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Instrument list pane
The console SHALL display a scrollable list of instruments in the left pane, filtered by the
currently selected asset class **and the currently active data sources in `SEG_SOURCE_FILTER`**.
Each list item SHALL show the instrument's `ticker` and `full_name`. Clicking an item SHALL load
that instrument's fundamentals in the main pane. The pane SHALL also contain a text input
(`INP_INSTRUMENT_FILTER`) above the list that filters the displayed rows live as the user types,
matching against `ticker` and `full_name` case-insensitively.

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
- **THEN** only rows whose `ticker` or `full_name` contain the typed string (case-insensitive)
  are visible; non-matching rows are hidden

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
