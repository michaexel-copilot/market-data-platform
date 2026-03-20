## Why

When a data source returns HTTP 404 for a given asset and interval, the scheduler continues retrying the request on every subsequent run, generating noise in logs and wasting API quota. Recording the 404 event and suppressing further fetches eliminates unnecessary calls and makes failures visible.

## What Changes

- New table `asset_not_found` to record `(instrument_id, data_source, interval)` triples that have returned 404, with timestamp and URL.
- The scheduler fetch logic detects HTTP 404 responses and writes a record to `asset_not_found`.
- Before each fetch, the scheduler checks whether the `(instrument_id, data_source, interval)` combination is already marked as not-found; if so, the fetch is skipped.

## Capabilities

### New Capabilities

- `asset-not-found-store`: Persistent store for 404 events per `(instrument_id, data_source, interval)`, including the triggering URL and timestamp. Provides read/write operations used by the fetch layer.

### Modified Capabilities

- `data-source-connectors`: The connector fetch loop gains pre-fetch suppression checks and post-404 recording, altering the observable retry behavior of each connector.

## Impact

- **Database**: New migration adding the `asset_not_found` table (PostgreSQL/TimescaleDB).
- **`src/market_data/ingestion/jobs.py`**: `_run_interval_job` (or equivalent per-connector dispatch) must catch HTTP 404, persist the event, and skip future fetches for the flagged combination.
- **`src/market_data/db/`**: New query helpers for inserting into and reading from `asset_not_found`.
- **No API/CLI surface changes** in this iteration — suppression is internal to the scheduler.
