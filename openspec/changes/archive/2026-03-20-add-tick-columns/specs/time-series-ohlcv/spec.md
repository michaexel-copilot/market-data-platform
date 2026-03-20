## MODIFIED Requirements

### Requirement: OHLCV time-series storage
The `ohlcv` table SHALL store multi-interval OHLCV bars with the PostgreSQL schema below. Column types are updated from DuckDB to PostgreSQL native types. The table SHALL be a TimescaleDB hypertable (managed by the `postgresql-backend` capability); the schema-level PRIMARY KEY constraint is retained.

```sql
CREATE TABLE IF NOT EXISTS ohlcv (
    instrument_id TEXT            NOT NULL,
    interval      TEXT            NOT NULL CHECK (interval IN ('1m', '5m', '1h', '1d')),
    ts            TIMESTAMPTZ     NOT NULL,
    open          DOUBLE PRECISION NOT NULL,
    high          DOUBLE PRECISION NOT NULL,
    low           DOUBLE PRECISION NOT NULL,
    close         DOUBLE PRECISION NOT NULL,
    volume        DOUBLE PRECISION,
    vwap          DOUBLE PRECISION,
    trade_count   INTEGER,
    market_cap    DOUBLE PRECISION,
    source        TEXT            NOT NULL,
    ingested_at   TIMESTAMPTZ     NOT NULL DEFAULT now(),
    tick_1h       BIGINT,
    CONSTRAINT ohlcv_tick_1h_not_null CHECK (interval != '1h' OR tick_1h IS NOT NULL),
    PRIMARY KEY (instrument_id, interval, ts)
);
```

#### Scenario: OHLCV upsert
- **WHEN** `INSERT INTO ohlcv ... ON CONFLICT (instrument_id, interval, ts) DO UPDATE SET open = excluded.open, ...` is executed
- **THEN** the row is inserted on first call and updated on subsequent calls for the same primary key

#### Scenario: Partial fields allowed
- **WHEN** a provider does not supply `vwap` or `trade_count` for a candle
- **THEN** those fields are stored as `NULL`; the row is accepted

#### Scenario: Time-range query
- **WHEN** `SELECT * FROM ohlcv WHERE instrument_id = %s AND interval = %s AND ts >= %s AND ts <= %s ORDER BY ts ASC` is executed
- **THEN** PostgreSQL uses hypertable chunk exclusion to scan only relevant monthly partitions

#### Scenario: 1h row missing tick_1h is rejected
- **WHEN** a row with `interval = '1h'` is inserted with `tick_1h = NULL`
- **THEN** the database rejects the row with a constraint violation

#### Scenario: Non-1h row with null tick_1h is accepted
- **WHEN** a row with `interval = '1m'`, `'5m'`, or `'1d'` is inserted with `tick_1h = NULL`
- **THEN** the row is accepted and stored

## ADDED Requirements

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

### Requirement: tick_1h backfill migration
The migration SHALL backfill `tick_1h` for all pre-existing rows in the `ohlcv` table where `interval = '1h'`. After the migration completes, no `interval = '1h'` row SHALL have `tick_1h = NULL`.

#### Scenario: Backfill sets correct value
- **WHEN** the migration runs on an `ohlcv` table containing 1h rows
- **THEN** each backfilled row has `tick_1h = EXTRACT(EPOCH FROM ts)::BIGINT / 3600`

#### Scenario: Backfill leaves non-1h rows unchanged
- **WHEN** the migration runs
- **THEN** rows with `interval != '1h'` retain `tick_1h = NULL`
