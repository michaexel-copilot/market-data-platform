## ADDED Requirements

### Requirement: Smart OHLCV update endpoint
The system SHALL expose `POST /v1/admin/smart-update-ohlcv` accepting a JSON body
`{ "instrument_id": "<id>" }`. The endpoint SHALL return HTTP 404 if the instrument does not
exist. On success the endpoint SHALL return HTTP 200 with a `steps` list and a
`total_written` integer.

#### Scenario: Unknown instrument returns 404
- **WHEN** `POST /v1/admin/smart-update-ohlcv` is called with an `instrument_id` that does not exist in the `instruments` table
- **THEN** the endpoint returns HTTP 404 with a detail message

#### Scenario: Response structure
- **WHEN** `POST /v1/admin/smart-update-ohlcv` is called with a valid instrument
- **THEN** the response body contains `{ "steps": [...], "total_written": N }` where `steps` is a list of objects each containing at minimum a `"step"` string key and a `"status"` string key

---

### Requirement: 1h freshness check step
The smart-update endpoint SHALL query `MAX(ts)` from the `ohlcv` table for the given
instrument at `interval = '1h'`. If the result is `NULL` or older than 5 hours relative to
the current UTC time, the step status SHALL be `"stale"`; otherwise `"fresh"`. The step
response object SHALL include the keys `last_ts` (ISO 8601 string or `null`) and
`threshold_hours` (integer `5`).

#### Scenario: No 1h data exists — stale
- **WHEN** the `ohlcv` table contains no `interval = '1h'` rows for the instrument
- **THEN** the `1h_freshness_check` step has `status = "stale"` and `last_ts = null`

#### Scenario: Recent 1h data exists — fresh
- **WHEN** the most recent `interval = '1h'` row for the instrument has `ts` within the last 5 hours
- **THEN** the `1h_freshness_check` step has `status = "fresh"`

#### Scenario: Stale 1h data — stale
- **WHEN** the most recent `interval = '1h'` row for the instrument has `ts` older than 5 hours
- **THEN** the `1h_freshness_check` step has `status = "stale"`

---

### Requirement: 1h ingest on stale data
When the `1h_freshness_check` step resolves as `"stale"`, the endpoint SHALL invoke the
`ohlcv_1h` ingestion job for the specific instrument (equivalent to
`_run_interval_job(Interval.ONE_HOUR, instrument_id=…, fill_gaps=True)`). The `1h_ingest`
step response SHALL include the key `written` (integer rows written by the ingest job).
When `1h_freshness_check` is `"fresh"`, the `1h_ingest` step SHALL have `status = "skipped"`
and `written = 0`.

#### Scenario: 1h ingest runs when stale
- **WHEN** `1h_freshness_check` returns `"stale"`
- **THEN** the `1h_ingest` step has `status = "ok"` and `written >= 0`

#### Scenario: 1h ingest skipped when fresh
- **WHEN** `1h_freshness_check` returns `"fresh"`
- **THEN** the `1h_ingest` step has `status = "skipped"` and `written = 0`

#### Scenario: 1h ingest error is captured
- **WHEN** the ingest job raises an exception
- **THEN** the `1h_ingest` step has `status = "error"` and an `error` key with the exception message; subsequent steps still execute

---

### Requirement: 1m gap detection
The smart-update endpoint SHALL query `MAX(ts)` from the `ohlcv` table for the given
instrument at `interval = '1m'`. The gap is defined as the interval from that timestamp (or
`now() - 5h` if no 1m data exists) to the current UTC time. The `1m_gap_check` step
response SHALL include `gap_start` (ISO 8601), `gap_hours` (float rounded to 2 decimal
places), and `status = "gap"` if `gap_hours > 0.1` else `"no_gap"`.

#### Scenario: Gap detected
- **WHEN** the most recent `interval = '1m'` row is more than 6 minutes old
- **THEN** `1m_gap_check` has `status = "gap"` and `gap_hours > 0.1`

#### Scenario: No gap
- **WHEN** the most recent `interval = '1m'` row is within the last 6 minutes
- **THEN** `1m_gap_check` has `status = "no_gap"`

---

### Requirement: Binance 1m availability check
The smart-update endpoint SHALL query `ohlcv_data_available JOIN data_source` to determine
whether `has_1m = TRUE AND short_name = 'binance'` for the given instrument. The
`binance_availability` step SHALL have `status = "available"` or `"unavailable"` accordingly.

#### Scenario: Binance 1m available
- **WHEN** `ohlcv_data_available` has a row for the instrument with `has_1m = TRUE` and the joined `data_source.short_name = 'binance'`
- **THEN** the `binance_availability` step has `status = "available"`

#### Scenario: Binance 1m unavailable
- **WHEN** no such row exists
- **THEN** the `binance_availability` step has `status = "unavailable"` and the fetch + aggregation steps have `status = "skipped"`

---

### Requirement: Binance 1m gap fill
When both `1m_gap_check` is `"gap"` and `binance_availability` is `"available"`, the
endpoint SHALL call `BinanceConnector.fetch_ohlcv` for `Interval.ONE_MIN` over the gap
range. The `1m_fetch` step response SHALL include `fetched` (integer count of records
returned). If the fetch raises an exception, the step SHALL have `status = "error"` with an
`error` key; the aggregation step SHALL be skipped.

#### Scenario: Successful fetch
- **WHEN** Binance returns candles for the gap range
- **THEN** `1m_fetch` has `status = "ok"` and `fetched` equals the number of records returned

#### Scenario: Empty fetch (pair not on Binance)
- **WHEN** Binance returns zero records (e.g. instrument is not traded on Binance)
- **THEN** `1m_fetch` has `status = "ok"` and `fetched = 0`; `1h_aggregation` has `status = "skipped"`

#### Scenario: Gap fill skipped — no gap
- **WHEN** `1m_gap_check` is `"no_gap"`
- **THEN** `1m_fetch` and `1h_aggregation` both have `status = "skipped"` with `reason = "no_gap"`

#### Scenario: Gap fill skipped — Binance unavailable
- **WHEN** `binance_availability` is `"unavailable"`
- **THEN** `1m_fetch` and `1h_aggregation` both have `status = "skipped"` with `reason = "binance_unavailable"`

---

### Requirement: 1m-to-1h aggregation
When `1m_fetch` returns one or more records, the endpoint SHALL aggregate them into 1h
candles using the following rules: bucket key = `ts` truncated to the start of the UTC hour;
`open` = first `open` in the bucket; `high` = maximum `high`; `low` = minimum `low`;
`close` = last `close`; `volume` = sum of all `volume` values (or `NULL` if all are `NULL`).
Each aggregated candle SHALL have `source = "aggregated:binance_1m"` and `is_aggregated =
True`. The candles SHALL be written via `write_ohlcv`. The `1h_aggregation` step SHALL
include `written` (integer rows upserted).

#### Scenario: Correct aggregation
- **WHEN** 60 1m records for the 14:00 UTC hour are fetched
- **THEN** one aggregated 1h candle is written with `ts = 14:00 UTC`, `open` from the 14:00 record, `high` = max across all 60, `low` = min, `close` from the 14:59 record, `volume` = sum

#### Scenario: Aggregated candle marked correctly
- **WHEN** an aggregated 1h candle is written
- **THEN** it has `is_aggregated = TRUE` and `source = "aggregated:binance_1m"` in the `ohlcv` table

#### Scenario: Partial bucket stored
- **WHEN** a gap ends mid-hour (e.g. current time is 14:37 UTC) and 37 1m records for 14:xx are fetched
- **THEN** one partial synthetic 1h candle covering 14:00 is written with the available data
