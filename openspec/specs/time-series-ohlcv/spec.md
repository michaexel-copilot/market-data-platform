# Time-Series OHLCV

## Purpose

Defines the OHLCV storage schema, native intervals, derived views, range query behaviour, and intraday archival policy for the platform's time-series market data.

## Requirements

### Requirement: OHLCV table schema
The system SHALL store OHLCV data in a single `ohlcv` table with columns: `instrument_id` (VARCHAR, NOT NULL), `interval` (VARCHAR: `1m`, `5m`, `1h`, `1d`), `ts` (TIMESTAMPTZ, NOT NULL), `open`, `high`, `low`, `close` (DOUBLE, NOT NULL), `volume`, `vwap`, `trade_count`, `market_cap` (nullable), `source` (VARCHAR), `ingested_at` (TIMESTAMPTZ). The PRIMARY KEY SHALL be `(instrument_id, interval, ts)`.

#### Scenario: OHLCV row inserted
- **WHEN** an ingestion job produces a candle for a given instrument, interval, and timestamp
- **THEN** a row is inserted into `ohlcv` with all non-null required fields populated and `ingested_at` set to the current UTC time

#### Scenario: Duplicate candle upserted
- **WHEN** a second ingestion run produces a candle for the same `(instrument_id, interval, ts)`
- **THEN** the existing row is replaced (`INSERT OR REPLACE`) and `ingested_at` is updated

#### Scenario: Partial fields allowed
- **WHEN** a provider does not supply `vwap` or `trade_count` for a candle
- **THEN** those fields are stored as `NULL`; the row is accepted

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
The system SHALL expose a `GET /v1/instruments/{symbol}/ohlcv-availability` endpoint that returns the first and last available timestamp per OHLCV interval for the given instrument. The response SHALL include entries for native intervals (`1m`, `5m`, `1h`, `1d`) queried from the `ohlcv` table, and derived intervals (`1w` from `ohlcv_weekly`, `4w` approximated from weekly data in 4-week buckets, `1mth` from `ohlcv_monthly`, `1y` and `1ytd` from daily data). Intervals with no data SHALL be omitted from the response.

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

#### Scenario: Empty instrument returns empty intervals
- **WHEN** `GET /v1/instruments/{symbol}/ohlcv-availability` is called and no OHLCV rows exist for that instrument
- **THEN** the response is `{ "instrument_id": "<id>", "intervals": {} }`

#### Scenario: Unknown symbol returns 404
- **WHEN** `GET /v1/instruments/nonexistent/ohlcv-availability` is called
- **THEN** the API returns HTTP 404
