## ADDED Requirements

### Requirement: Hyperliquid data source registration
The system SHALL register Hyperliquid as a data source in the `data_source` table with
`short_name = 'hl'`, `name = 'Hyperliquid'`, and `data_source_id = 3` via migration
`023_hl_data_source.sql`. The row SHALL be inserted idempotently (`ON CONFLICT DO NOTHING`).

#### Scenario: Migration seeds hl row
- **WHEN** migration `023_hl_data_source.sql` is applied to a database that does not yet contain
  a row with `data_source_id = 3`
- **THEN** a row with `short_name = 'hl'` and `name = 'Hyperliquid'` is present in `data_source`

#### Scenario: Re-applying migration is idempotent
- **WHEN** migration `023_hl_data_source.sql` is applied a second time
- **THEN** no error is raised and the `data_source` table still contains exactly one row with
  `short_name = 'hl'`

---

### Requirement: Instrument source intersection table
The system SHALL maintain an `instrument_source_intersection` table that stores one row per
instrument-source pair, defined as:
```sql
CREATE TABLE instrument_source_intersection (
    instrument_id     TEXT NOT NULL REFERENCES instruments(instrument_id) ON DELETE CASCADE,
    source_short_name TEXT NOT NULL,
    PRIMARY KEY (instrument_id, source_short_name)
);
```
The `source_short_name` column SHALL store the `short_name` value from the `data_source` table
but is not constrained by a foreign key to allow seeding before data sources are fully registered.

#### Scenario: Table created by migration
- **WHEN** migration `024_instrument_source_intersection.sql` is applied
- **THEN** the `instrument_source_intersection` table exists with the composite primary key
  `(instrument_id, source_short_name)`

#### Scenario: Cascade delete
- **WHEN** an instrument row is deleted from `instruments`
- **THEN** all corresponding rows in `instrument_source_intersection` are deleted automatically

---

### Requirement: Import source intersection CLI command
The system SHALL provide a CLI command `uv run import-source-intersection` that reads
`/appdata/static_data/cc_hl_intersection.csv` and populates `instrument_source_intersection`.
For each row in the CSV, the command SHALL attempt to match the `base` column against
`instruments.ticker` (case-insensitive) for `asset_class = 'crypto'`. For matched instruments
it SHALL upsert one row with `source_short_name = 'eodhd'` and one row with
`source_short_name = 'hl'`. Rows for instruments not found in the registry SHALL be skipped and
counted as unmatched. The command SHALL print a summary: matched, skipped (unmatched), and total
CSV rows processed. The command SHALL be idempotent: re-running it produces no duplicates and no
errors.

#### Scenario: Successful import
- **WHEN** `uv run import-source-intersection` is run and the CSV contains N rows that all match
  instruments in the registry
- **THEN** `instrument_source_intersection` contains 2×N rows (one `eodhd` and one `hl` per
  instrument) and the summary prints `matched=N, skipped=0`

#### Scenario: Unmatched ticker skipped
- **WHEN** the CSV contains a `base` value that has no matching row in `instruments`
- **THEN** no row is inserted for that ticker and the summary counts it as skipped

#### Scenario: Idempotent re-run
- **WHEN** `uv run import-source-intersection` is run a second time without changes to the CSV
- **THEN** no error is raised, row counts are unchanged, and no duplicate rows exist

#### Scenario: Missing CSV file
- **WHEN** `/appdata/static_data/cc_hl_intersection.csv` does not exist
- **THEN** the command exits with a non-zero exit code and prints a clear error message
  indicating the missing file path
