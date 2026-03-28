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
    tick_1h       BIGINT,
    tick_1d       BIGINT,
    is_aggregated BOOLEAN          NOT NULL DEFAULT FALSE,
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

## ADDED Requirements

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
