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
    PRIMARY KEY (instrument_id, interval, ts)
);
```

#### Scenario: OHLCV upsert
- **WHEN** `INSERT INTO ohlcv ... ON CONFLICT (instrument_id, interval, ts) DO UPDATE SET open = excluded.open, ...` is executed
- **THEN** the row is inserted on first call and updated on subsequent calls for the same primary key

#### Scenario: Time-range query
- **WHEN** `SELECT * FROM ohlcv WHERE instrument_id = %s AND interval = %s AND ts >= %s AND ts <= %s ORDER BY ts ASC` is executed
- **THEN** PostgreSQL uses hypertable chunk exclusion to scan only relevant monthly partitions
