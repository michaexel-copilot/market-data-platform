## ADDED Requirements

### Requirement: Backtest history table has a heading
The backtest history section SHALL display a visible heading "Cached Backtests" above the table so the user can identify the section at a glance.

#### Scenario: Heading visible when results exist
- **WHEN** the backtest history partial renders with one or more cached results
- **THEN** the text "Cached Backtests" SHALL appear as a heading above the table

#### Scenario: Heading visible when no results
- **WHEN** the backtest history partial renders with no cached results
- **THEN** the heading SHALL still be present above the empty-state message

### Requirement: Table columns are client-side sortable
Each data column header in the backtest history table SHALL be clickable to sort the rows by that column.

#### Scenario: First click sorts ascending
- **WHEN** the user clicks a column header for the first time (or after a reset)
- **THEN** the table rows SHALL be reordered ascending by that column's values
- **THEN** the header SHALL display an ascending indicator (▲)

#### Scenario: Second click sorts descending
- **WHEN** the user clicks a column header that is already sorted ascending
- **THEN** the table rows SHALL be reordered descending by that column's values
- **THEN** the header SHALL display a descending indicator (▼)

#### Scenario: Numeric columns sort numerically
- **WHEN** sorting a column containing monetary values (P&L) or counts (Val Trades)
- **THEN** rows SHALL be ordered by numeric value, not lexicographic order

#### Scenario: String columns sort alphabetically
- **WHEN** sorting a text column (e.g. Ind 1, Ind 2, Exposure, dates)
- **THEN** rows SHALL be ordered by locale-aware string comparison

#### Scenario: Sort resets on table refresh
- **WHEN** the backtest history partial is refreshed via HTMX (e.g. after a new backtest run)
- **THEN** the table SHALL render in default (newest-first) order with no sort indicator active
