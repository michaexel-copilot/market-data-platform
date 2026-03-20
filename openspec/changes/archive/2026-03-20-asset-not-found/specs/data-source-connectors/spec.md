# Data Source Connectors — Delta Spec

## ADDED Requirements

### Requirement: Pre-fetch 404 suppression check
Before executing a fetch for any `(instrument_id, connector, interval)` combination, the
ingestion engine SHALL consult the `asset_not_found` store. If the combination is present,
the fetch SHALL be skipped entirely without logging a warning. The blocked set SHALL be
loaded once per interval job run (not per individual fetch) and held in memory for the
duration of that run.

#### Scenario: Blocked combination is skipped
- **WHEN** `_run_interval_job` starts for interval `'5m'` and `asset_not_found` contains a row for `(instrument_id='home3', data_source='eodhd', interval='5m')`
- **THEN** `conn.fetch_ohlcv('home3', ...)` is never called for the eodhd connector during that run

#### Scenario: Non-blocked combination proceeds normally
- **WHEN** `_run_interval_job` starts and `asset_not_found` has no row for a given `(instrument_id, data_source, interval)`
- **THEN** the fetch proceeds as before, unaffected by the suppression check

#### Scenario: Blocked set is loaded once per job run
- **WHEN** `_run_interval_job` runs for an interval with 50 instruments and 10 connectors
- **THEN** `load_blocked` is called exactly once (not 500 times), and the returned `frozenset` is reused for every fetch decision within that run

---

### Requirement: Record 404 responses from connectors
When a connector fetch raises `httpx.HTTPStatusError` with `status_code == 404`, the
ingestion engine SHALL call `record_not_found` with the `instrument_id`, `conn.name`,
the string representation of the interval, and the URL from the exception's response
object. Processing SHALL continue with the next instrument after recording.

#### Scenario: 404 is recorded and processing continues
- **WHEN** `conn.fetch_ohlcv(instrument_id, interval, ...)` raises `httpx.HTTPStatusError` with status 404
- **THEN** `record_not_found(conn, instrument_id, conn.name, interval, url)` is called, a `logger.info` message is emitted, and the loop advances to the next instrument (no `break`)

#### Scenario: 404 does not disable the connector
- **WHEN** a 404 is recorded for one instrument on a connector
- **THEN** the connector is NOT disabled via `registry.disable()` and continues to be used for other instruments in the same run

#### Scenario: 404 handling is distinct from other HTTP errors
- **WHEN** a connector raises `httpx.HTTPStatusError` with status 404
- **THEN** only the 404 branch executes; the generic HTTP warning branch does NOT also execute for the same error
