# OHLCV Cache Importer

## Purpose

Defines the local-cache import capability that reads pre-downloaded provider data files from the `/appdata` directory tree,
parses them, and upserts the records into the `ohlcv` table.

## Requirements

### Requirement: Cache folder path convention
The system SHALL resolve the cache folder for a given `(source_short_name, interval)` pair using the path:
```
$APPDATA_DIR/<source_short_name>/<data_class>/<interval_label>
```
where `APPDATA_DIR` defaults to `/appdata` and is overridable via the `APPDATA_DIR` environment variable.
The `(data_class, interval_label)` mapping SHALL be:

| Interval | data_class | interval_label |
|---|---|---|
| 1m | intraday_historical_data | 1-minute |
| 5m | intraday_historical_data | 5-minute |
| 1h | intraday_historical_data | 1-hour |
| 1d | eod_historical_data | 1-day |

#### Scenario: Path resolved for 1h eodhd
- **WHEN** `source_short_name = "eodhd"` and `interval = "1h"` and `APPDATA_DIR = "/appdata"`
- **THEN** the resolved path is `/appdata/eodhd/intraday_historical_data/1-hour`

#### Scenario: Custom APPDATA_DIR respected
- **WHEN** `APPDATA_DIR = "/data/cache"` and `source_short_name = "eodhd"` and `interval = "1d"`
- **THEN** the resolved path is `/data/cache/eodhd/eod_historical_data/1-day`

---

### Requirement: Folder existence check
Before scanning for files, the system SHALL verify that the resolved cache folder exists. If it does not exist, the system SHALL return a structured error response containing `status = "folder_not_found"` and `expected_path` (the full resolved path). No exception SHALL be raised to the caller.

#### Scenario: Folder exists
- **WHEN** the resolved cache folder is present on disk
- **THEN** the import proceeds to file scanning

#### Scenario: Folder does not exist
- **WHEN** the resolved cache folder is absent
- **THEN** the function returns `{status: "folder_not_found", expected_path: "<path>"}` without raising an exception

---

### Requirement: File-to-instrument matching
The system SHALL scan all `.json` and `.csv` files in the cache folder. A file SHALL be considered a match for the target instrument if the file's stem (name without extension) equals `instrument_id` OR `ticker` (case-insensitive comparison). All matching files SHALL be processed.

#### Scenario: Match by instrument_id
- **WHEN** a file named `bitcoin.json` exists and `instrument_id = "bitcoin"`
- **THEN** the file is included in the import

#### Scenario: Match by ticker
- **WHEN** a file named `BTC.json` exists and `ticker = "BTC"`
- **THEN** the file is included in the import (case-insensitive)

#### Scenario: No matching files
- **WHEN** no files in the folder match the instrument
- **THEN** the function returns `{status: "ok", rows_imported: 0, files_processed: 0}` without error

---

### Requirement: JSON file parsing
The system SHALL parse JSON files as arrays of OHLCV objects. Two shapes SHALL be supported:

- **Intraday** (intervals `1m`, `5m`, `1h`): each object has `datetime` (string `"YYYY-MM-DD HH:MM:SS"`), `open`, `high`, `low`, `close`, `volume`
- **EOD** (interval `1d`): each object has `date` (string `"YYYY-MM-DD"`), `open`, `high`, `low`, `close`, `volume`

Timestamps SHALL be interpreted as UTC. The `vwap`, `trade_count`, and `market_cap` fields SHALL be set to `None` if absent.

#### Scenario: Intraday JSON parsed
- **WHEN** a JSON file contains `[{"datetime": "2024-01-01 14:00:00", "open": 42000.0, "high": 43000.0, "low": 41000.0, "close": 42500.0, "volume": 12345.0}]`
- **THEN** one `OHLCVRecord` is produced with `ts = 2024-01-01T14:00:00Z` and the correct OHLCV values

#### Scenario: EOD JSON parsed
- **WHEN** a JSON file contains `[{"date": "2024-01-01", "open": 42000.0, "high": 43000.0, "low": 41000.0, "close": 42500.0, "volume": 12345.0}]`
- **THEN** one `OHLCVRecord` is produced with `ts = 2024-01-01T00:00:00Z`

---

### Requirement: CSV file parsing
The system SHALL parse CSV files with a header row. Recognised column names: `datetime` or `date`, `open`, `high`, `low`, `close`, `volume`. Column order is arbitrary; additional columns are ignored. Timestamp interpretation SHALL follow the same rules as for JSON.

#### Scenario: CSV with standard columns parsed
- **WHEN** a CSV file has columns `datetime,open,high,low,close,volume` with one data row
- **THEN** one `OHLCVRecord` is produced with correct values

---

### Requirement: OHLCV upsert after parse
After parsing all matching files, the system SHALL call `write_ohlcv()` with all collected `OHLCVRecord` objects. Each record SHALL have `instrument_id` set to the requested instrument, `interval` set to the requested interval, and `source` set to the data source `short_name`. The function SHALL return `{status: "ok", rows_imported: N, files_processed: M}`.

#### Scenario: Records written
- **WHEN** two matching files are parsed yielding 500 records total
- **THEN** `write_ohlcv()` is called once with all 500 records and `{status: "ok", rows_imported: 500, files_processed: 2}` is returned

---

### Requirement: Best-fit source resolution API
The system SHALL expose `POST /v1/admin/import-ohlcv-cache` accepting a JSON body with `instrument_id` (string) and `interval` (string). The endpoint SHALL resolve the best data source by querying `ohlcv_data_available JOIN data_source` filtering on `has_<interval> = true` for the instrument, ordered by `retrieval_priority ASC NULLS LAST`. It SHALL then invoke the cache importer and return the structured result.

If no eligible source is found, the endpoint SHALL return HTTP 422 with `{"detail": "No data source covers interval <interval> for this instrument"}`.

#### Scenario: Source resolved and import succeeds
- **WHEN** `POST /v1/admin/import-ohlcv-cache` is called with a valid `instrument_id` and `interval`
- **THEN** the best-priority eligible source is selected, the import runs, and `{status, rows_imported, files_processed}` is returned with HTTP 200

#### Scenario: No eligible source
- **WHEN** no `ohlcv_data_available` row exists with `has_<interval> = true` for the instrument
- **THEN** HTTP 422 is returned with an explanatory detail message

#### Scenario: Folder not found propagated
- **WHEN** the resolved cache folder does not exist
- **THEN** HTTP 200 is returned with `{status: "folder_not_found", expected_path: "...", source_short_name: "..."}`

---
