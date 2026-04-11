# Time-Series OHLCV

## Purpose

Defines the OHLCV storage schema, native intervals, derived views, range query behaviour, and intraday archival policy for the platform's time-series market data.

## Requirements

### Requirement: OHLCV time-series storage
The `ohlcv` table SHALL store multi-interval OHLCV bars with the PostgreSQL schema below.
Column types are updated from DuckDB to PostgreSQL native types. The table SHALL be a
TimescaleDB hypertable (managed by the `postgresql-backend` capability); the schema-level
PRIMARY KEY constraint is retained.

```sql
CREATE TABLE IF NOT EXISTS ohlcv (
    instrument_id TEXT             NOT NULL,
    interval      TEXT             NOT NULL CHECK (interval IN ('1m', '5m', '1h', '1d')),
    ts            TIMESTAMPTZ      NOT NULL,
    open          DOUBLE PRECISION NOT NULL,
    high          DOUBLE PRECISION NOT NULL,
    low           DOUBLE PRECISION NOT NULL,
    close         DOUBLE PRECISION NOT NULL,
    volume        DOUBLE PRECISION,
    vwap          DOUBLE PRECISION,
    trade_count   INTEGER,
    market_cap    DOUBLE PRECISION,
    source        TEXT             NOT NULL,
    ingested_at   TIMESTAMPTZ      NOT NULL DEFAULT now(),
    tick_1m       BIGINT,
    tick_1h       BIGINT,
    tick_1d       BIGINT,
    is_aggregated BOOLEAN          NOT NULL DEFAULT FALSE,
    CONSTRAINT ohlcv_tick_1m_not_null CHECK (interval != '1m' OR tick_1m IS NOT NULL),
    CONSTRAINT ohlcv_tick_1h_not_null CHECK (interval != '1h' OR tick_1h IS NOT NULL),
    PRIMARY KEY (instrument_id, interval, ts)
);
```

`is_aggregated = FALSE` (the default) means the candle was ingested directly from a primary
data source. `is_aggregated = TRUE` means the candle was synthesised from a finer-grained
interval (e.g. 1h aggregated from Binance 1m data).

#### Scenario: OHLCV upsert
- **WHEN** `INSERT INTO ohlcv ... ON CONFLICT (instrument_id, interval, ts) DO UPDATE SET open = excluded.open, ...` is executed
- **THEN** the row is inserted on first call and updated on subsequent calls for the same primary key

#### Scenario: Partial fields allowed
- **WHEN** a provider does not supply `vwap` or `trade_count` for a candle
- **THEN** those fields are stored as `NULL`; the row is accepted

#### Scenario: Time-range query
- **WHEN** `SELECT * FROM ohlcv WHERE instrument_id = %s AND interval = %s AND ts >= %s AND ts <= %s ORDER BY ts ASC` is executed
- **THEN** PostgreSQL uses hypertable chunk exclusion to scan only relevant monthly partitions

#### Scenario: 1m row missing tick_1m is rejected
- **WHEN** a row with `interval = '1m'` is inserted with `tick_1m = NULL`
- **THEN** the database rejects the row with a constraint violation

#### Scenario: Writer computes tick_1m for 1m candle
- **WHEN** the ingestion writer processes an `OHLCVRecord` with `interval = '1m'`
- **THEN** the inserted row has `tick_1m = floor(unix_epoch_seconds(ts) / 60)`

#### Scenario: 1h row missing tick_1h is rejected
- **WHEN** a row with `interval = '1h'` is inserted with `tick_1h = NULL`
- **THEN** the database rejects the row with a constraint violation

#### Scenario: Non-1h row with null tick_1h is accepted
- **WHEN** a row with `interval = '1m'`, `'5m'`, or `'1d'` is inserted with `tick_1h = NULL`
- **THEN** the row is accepted and stored

#### Scenario: is_aggregated defaults to FALSE
- **WHEN** a candle is inserted without specifying `is_aggregated`
- **THEN** the stored row has `is_aggregated = FALSE`

---

### Requirement: Aggregated candle precedence in upsert
The ingestion writer SHALL implement conflict-resolution semantics that give primary-source
candles precedence over aggregated candles:

- If the **incoming** candle has `is_aggregated = FALSE` (real data), it SHALL always
  overwrite the existing row regardless of the existing row's `is_aggregated` value.
- If the **incoming** candle has `is_aggregated = TRUE` (synthetic), it SHALL only update
  the existing row if the existing row also has `is_aggregated = TRUE`. It SHALL NOT
  overwrite a row where `is_aggregated = FALSE`.

This is implemented as a single `ON CONFLICT DO UPDATE` clause with `CASE WHEN` guards on
every updated column.

#### Scenario: Real data overwrites aggregated
- **WHEN** an aggregated 1h candle (`is_aggregated = TRUE`) exists for `(BTC, 1h, 14:00 UTC)` and a real 1h candle (`is_aggregated = FALSE`) is upserted for the same key
- **THEN** the stored row has the real candle's OHLCV values and `is_aggregated = FALSE`

#### Scenario: Aggregated data does not overwrite real data
- **WHEN** a real 1h candle (`is_aggregated = FALSE`) exists for `(BTC, 1h, 14:00 UTC)` and an aggregated candle (`is_aggregated = TRUE`) is upserted for the same key
- **THEN** the stored row is unchanged — original OHLCV values and `is_aggregated = FALSE` are preserved

#### Scenario: Aggregated data overwrites aggregated data
- **WHEN** an aggregated 1h candle exists and a new aggregated candle is upserted for the same key
- **THEN** the stored row is updated with the new candle's values

#### Scenario: Real data overwrites real data
- **WHEN** two real candles are upserted for the same key
- **THEN** the second upsert overwrites the first (standard behaviour unchanged)

---

### Requirement: Native intervals
The system SHALL ingest and store OHLCV data at native intervals of `1m`, `5m`, `1h`, and `1d`. No other intervals are stored natively.

#### Scenario: Valid interval accepted
- **WHEN** an ingestion job writes a candle with `interval = '1h'`
- **THEN** the row is accepted and stored

#### Scenario: Invalid interval rejected
- **WHEN** an ingestion job attempts to write a candle with `interval = '15m'`
- **THEN** the row is rejected with a validation error before any DB write

---

### Requirement: Derived weekly and monthly views
The system SHALL provide `ohlcv_weekly` and `ohlcv_monthly` as DuckDB views derived from the `1d` native data. Weekly view aggregates by 7-day buckets (Monday-aligned). Monthly view aggregates by calendar month. Both views expose: `instrument_id`, `interval` (literal `'1w'` / `'1mo'`), `ts` (bucket start), `open` (first), `high` (max), `low` (min), `close` (last), `volume` (sum).

#### Scenario: Weekly data queried
- **WHEN** a caller queries `ohlcv_weekly` for a given instrument
- **THEN** rows are returned with Monday-aligned weekly buckets, OHLC aggregated correctly, and `interval = '1w'`

#### Scenario: Monthly data queried
- **WHEN** a caller queries `ohlcv_monthly` for a given instrument
- **THEN** rows are returned with calendar-month-start timestamps, OHLC aggregated correctly, and `interval = '1mo'`

#### Scenario: Derived views reflect latest daily data
- **WHEN** new `1d` candles are inserted
- **THEN** `ohlcv_weekly` and `ohlcv_monthly` immediately reflect the new data (views are not materialised; they query live)

---

### Requirement: Time-series range query
The API layer SHALL support querying `ohlcv` (and derived views) by `instrument_id`, `interval`, and an optional `[since, until]` time range. Results SHALL be returned in ascending `ts` order.

#### Scenario: Range query with both bounds
- **WHEN** a caller requests OHLCV for `instrument_id=X`, `interval=1h`, `since=2026-01-01`, `until=2026-02-01`
- **THEN** only rows within that range (inclusive) are returned, sorted by `ts` ascending

#### Scenario: Open-ended query (no until)
- **WHEN** a caller provides `since` but omits `until`
- **THEN** all rows from `since` to the latest available timestamp are returned

#### Scenario: Empty range returns empty result
- **WHEN** a caller requests a range for which no data exists
- **THEN** an empty result set is returned (not an error)

---

### Requirement: Intraday data archival
The system SHALL archive `1m` and `5m` rows older than 90 days to Parquet files and remove them from the live `ohlcv` table. Archived Parquet files SHALL remain queryable via DuckDB's native Parquet scan.

#### Scenario: Archive job runs
- **WHEN** the archive job executes
- **THEN** all `1m` and `5m` rows with `ts < now() - 90 days` are exported to `archive/ohlcv_{interval}_{date}.parquet` and deleted from the `ohlcv` table

#### Scenario: Archived data remains queryable
- **WHEN** a caller queries historical 1m data older than 90 days
- **THEN** the system reads the relevant Parquet archive file(s) and returns results

---

### Requirement: OHLCV availability endpoint
The system SHALL expose a `GET /v1/instruments/{symbol}/ohlcv-availability` endpoint that returns the first and last available timestamp per OHLCV interval for the given instrument. The response SHALL include entries for native intervals (`1m`, `5m`, `1h`, `1d`) queried from the `ohlcv` table, and derived intervals (`1w` from `ohlcv_weekly`, `4w` approximated from weekly data in 4-week buckets, `1mth` from `ohlcv_monthly`, `1y` and `1ytd` from daily data).

The `1m` interval SHALL always be present in the response, even when no `1m` rows exist for the instrument. In that case the response SHALL contain `"1m": { "first": null, "last": null }`.

Response schema:
```json
{
  "instrument_id": "<id>",
  "intervals": {
    "<interval>": { "first": "<ISO8601>", "last": "<ISO8601>" }
  }
}
```

#### Scenario: Availability returned for populated instrument
- **WHEN** `GET /v1/instruments/bitcoin/ohlcv-availability` is called and the `ohlcv` table contains `1d` rows for `bitcoin`
- **THEN** the response contains an `intervals.1d` entry with `first` and `last` timestamps

#### Scenario: Empty 1m availability still shown
- **WHEN** `GET /v1/instruments/{symbol}/ohlcv-availability` is called for an instrument with no `1m` rows but with other OHLCV data present
- **THEN** the response still includes `intervals.1m = { "first": null, "last": null }`

#### Scenario: Unknown symbol returns 404
- **WHEN** `GET /v1/instruments/nonexistent/ohlcv-availability` is called
- **THEN** the API returns HTTP 404

---

### Requirement: Per-interval OHLCV update settings
The system SHALL persist a per-instrument per-interval `auto_update` flag in the `ohlcv_update_settings` table.

```sql
CREATE TABLE IF NOT EXISTS ohlcv_update_settings (
    instrument_id VARCHAR NOT NULL REFERENCES instruments(instrument_id) ON DELETE CASCADE,
    interval VARCHAR NOT NULL,
    auto_update BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (instrument_id, interval)
);
```

The system SHALL expose:
- `GET /v1/instruments/{symbol}/ohlcv-update-settings`
- `PUT /v1/instruments/{symbol}/ohlcv-update-settings/{interval}`

The GET response SHALL return all native intervals (`1m`, `5m`, `1h`, `1d`) with explicit `auto_update` booleans, defaulting to `false` when no row exists yet.
The PUT endpoint SHALL upsert the requested interval row.

#### Scenario: Default settings returned for new instrument
- **WHEN** no rows exist yet in `ohlcv_update_settings` for an instrument
- **THEN** `GET /v1/instruments/{symbol}/ohlcv-update-settings` returns all native intervals with `auto_update = false`

#### Scenario: Put setting persists value
- **WHEN** `PUT /v1/instruments/{symbol}/ohlcv-update-settings/1h` is called with `{ "auto_update": true }`
- **THEN** the value is upserted and a subsequent GET returns `intervals.1h.auto_update = true`

### Requirement: Per-interval manual OHLCV update endpoint
The system SHALL expose `POST /v1/instruments/{symbol}/update-ohlcv/{interval}` for native intervals.

- For `1m`, the endpoint SHALL fetch candles from Binance and write returned rows into `ohlcv`.
- For `5m`, `1h`, and `1d`, the endpoint SHALL aggregate from the best available **newer** lower interval already stored in `ohlcv`.
- If no newer lower-resolution source data exists, the endpoint SHALL return HTTP 422 with an actionable message telling the operator to refresh `1m` first.
- On success, the response SHALL include `instrument_id`, `interval`, `source_interval`, `written`, and a human-readable `message`.

#### Scenario: 1m update writes Binance rows
- **WHEN** `POST /v1/instruments/{symbol}/update-ohlcv/1m` returns two Binance candles
- **THEN** the endpoint responds with `written = 2` and the rows are stored with non-null `tick_1m`

#### Scenario: 1h update rejects stale 5m source
- **WHEN** the most recent `1h` candle is newer than the most recent available `5m` candle and no newer `1m` data exists
- **THEN** `POST /v1/instruments/{symbol}/update-ohlcv/1h` returns HTTP 422 instead of claiming a successful update from stale data

#### Scenario: 1d update aggregates from newer 1h data
- **WHEN** the instrument has newer `1h` candles than its latest `1d` candle
- **THEN** `POST /v1/instruments/{symbol}/update-ohlcv/1d` aggregates from `1h` and returns a success response showing `source_interval = "1h"`

---

### Requirement: tick_1h population on ingestion
The ingestion writer SHALL compute and populate `tick_1h` for every candle with `interval = '1h'`. `tick_1h` SHALL be defined as `floor(unix_epoch_seconds(ts) / 3600)`, i.e. the number of complete 1-hour intervals elapsed since 1970-01-01T00:00:00Z. For all other intervals, `tick_1h` SHALL be omitted (written as `NULL`).

#### Scenario: Writer computes tick_1h for 1h candle
- **WHEN** the ingestion writer processes an `OHLCVRecord` with `interval = '1h'` and `ts = 2026-01-01T06:00:00Z`
- **THEN** the inserted row has `tick_1h = 491334` (i.e. `1735714800 / 3600`)

#### Scenario: Writer omits tick_1h for non-1h candle
- **WHEN** the ingestion writer processes an `OHLCVRecord` with `interval = '1m'`
- **THEN** the inserted row has `tick_1h = NULL`

#### Scenario: Upsert preserves tick_1h
- **WHEN** a 1h candle is upserted for an already-existing row
- **THEN** `tick_1h` is updated to the value from the incoming record (not kept from the old row)

---

### Requirement: tick_1h backfill migration
The migration SHALL backfill `tick_1h` for all pre-existing rows in the `ohlcv` table where `interval = '1h'`. After the migration completes, no `interval = '1h'` row SHALL have `tick_1h = NULL`.

#### Scenario: Backfill sets correct value
- **WHEN** the migration runs on an `ohlcv` table containing 1h rows
- **THEN** each backfilled row has `tick_1h = EXTRACT(EPOCH FROM ts)::BIGINT / 3600`

#### Scenario: Backfill leaves non-1h rows unchanged
- **WHEN** the migration runs
- **THEN** rows with `interval != '1h'` retain `tick_1h = NULL`
