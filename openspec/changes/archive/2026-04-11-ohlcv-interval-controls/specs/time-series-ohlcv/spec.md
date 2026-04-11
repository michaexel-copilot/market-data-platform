## MODIFIED Requirements

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

#### Scenario: 1m row missing tick_1m is rejected
- **WHEN** a row with `interval = '1m'` is inserted with `tick_1m = NULL`
- **THEN** the database rejects the row with a constraint violation

#### Scenario: Writer computes tick_1m for 1m candle
- **WHEN** the ingestion writer processes an `OHLCVRecord` with `interval = '1m'`
- **THEN** the inserted row has `tick_1m = floor(unix_epoch_seconds(ts) / 60)`

---

### Requirement: OHLCV availability endpoint
The system SHALL expose a `GET /v1/instruments/{symbol}/ohlcv-availability` endpoint that returns the first and last available timestamp per OHLCV interval for the given instrument. The response SHALL include entries for native intervals (`1m`, `5m`, `1h`, `1d`) queried from the `ohlcv` table, and derived intervals (`1w` from `ohlcv_weekly`, `4w` approximated from weekly data in 4-week buckets, `1mth` from `ohlcv_monthly`, `1y` and `1ytd` from daily data).

The `1m` interval SHALL always be present in the response, even when no 1m rows exist for the instrument. In that case the response SHALL contain `"1m": { "first": null, "last": null }`.

#### Scenario: Empty 1m availability still shown
- **WHEN** `GET /v1/instruments/{symbol}/ohlcv-availability` is called for an instrument with no `1m` rows but with other OHLCV data present
- **THEN** the response still includes `intervals.1m = { "first": null, "last": null }`

---

## ADDED Requirements

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
