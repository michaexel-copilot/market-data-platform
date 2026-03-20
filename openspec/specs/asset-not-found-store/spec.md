# Asset Not Found Store

## Purpose

Persistent store for HTTP 404 "asset not found" events raised by data source connectors.
Records `(instrument_id, data_source, interval)` triples that have produced a 404 response,
enabling the ingestion layer to suppress future fetches for those combinations.

## Requirements

### Requirement: Asset-not-found table
The system SHALL maintain a table `asset_not_found` with a composite primary key of
`(instrument_id, data_source, interval)`. It SHALL store the URL that produced the first
404, plus `first_seen_at` and `last_seen_at` timestamps (both `TIMESTAMPTZ NOT NULL`).

#### Scenario: Table created by migration
- **WHEN** migration `028_asset_not_found.sql` is applied to a database that does not yet have the table
- **THEN** the `asset_not_found` table exists with columns `instrument_id TEXT`, `data_source TEXT`, `interval TEXT`, `url TEXT`, `first_seen_at TIMESTAMPTZ`, `last_seen_at TIMESTAMPTZ` and a PRIMARY KEY on `(instrument_id, data_source, interval)`

---

### Requirement: Record a 404 event
The system SHALL provide a write operation `record_not_found(conn, instrument_id, data_source, interval, url)` that inserts a new row if the combination is not yet known, or updates `last_seen_at` to `NOW()` if it is. The `url` column SHALL NOT be overwritten on subsequent 404s; only `last_seen_at` is updated.

#### Scenario: First 404 for a new combination
- **WHEN** `record_not_found` is called for a `(instrument_id, data_source, interval)` triple that has no existing row
- **THEN** a new row is inserted with `url` set to the provided URL and both `first_seen_at` and `last_seen_at` set to the current time

#### Scenario: Repeated 404 for a known combination
- **WHEN** `record_not_found` is called for a `(instrument_id, data_source, interval)` triple that already has a row
- **THEN** `last_seen_at` is updated to the current time and `url` and `first_seen_at` are unchanged

---

### Requirement: Query blocked combinations by interval
The system SHALL provide a read operation `load_blocked(conn, interval) -> frozenset[tuple[str, str]]` that returns all `(instrument_id, data_source)` pairs present in `asset_not_found` for the given interval. The result SHALL be returned as a `frozenset` for O(1) membership testing.

#### Scenario: Load blocked set for an interval with entries
- **WHEN** `load_blocked` is called for `interval = '5m'` and the table contains rows for that interval
- **THEN** the function returns a `frozenset` containing exactly the `(instrument_id, data_source)` pairs for all `'5m'` rows

#### Scenario: Load blocked set for an interval with no entries
- **WHEN** `load_blocked` is called for an interval that has no rows in `asset_not_found`
- **THEN** the function returns an empty `frozenset`
