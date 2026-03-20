## Context

The `ohlcv` table is a TimescaleDB hypertable defined in `008_ohlcv.sql` and managed through sequential numbered SQL migrations in `src/market_data/db/migrations_pg/`. OHLCV rows are written via `src/market_data/ingestion/writer.py` using a batch upsert on `(instrument_id, interval, ts)`. The `OHLCVRecord` model in `src/market_data/models/ohlcv.py` is the data contract between parsers and the writer.

Currently, detecting gaps or duplicates in the 1h series requires timestamp arithmetic on every row. A pre-computed integer tick (`tick_1h = seconds_since_epoch / 3600`) makes this O(1) per row and enables simple uniqueness assertions.

## Goals / Non-Goals

**Goals:**
- Add `tick_1h BIGINT` column to `ohlcv`, enforced NOT NULL for `interval = '1h'` rows
- Backfill all existing `interval = '1h'` rows
- Populate `tick_1h` in the writer for 1h candles during new upserts

**Non-Goals:**
- Tick columns for other intervals (`1m`, `5m`, `1d`) — deferred to a future change
- Uniqueness index on `tick_1h` — not required now; the existing PK on `(instrument_id, interval, ts)` already prevents duplicates
- Changes to the REST or gRPC API layer

## Decisions

### D1: Column name `tick_1h`, nullable for non-1h rows

`tick_1h` is interval-specific; storing `NULL` for `interval != '1h'` rows is simpler than splitting the table or adding a polymorphic tick column. A `CHECK` constraint enforces correctness for 1h rows:

```sql
CHECK (interval != '1h' OR tick_1h IS NOT NULL)
```

_Alternative considered_: A single `tick` column with no interval suffix — rejected because the semantics differ per interval and adding further tick columns later (e.g., `tick_1d`) would be ambiguous.

### D2: Tick formula — integer division of Unix epoch seconds

```sql
tick_1h = EXTRACT(EPOCH FROM ts)::BIGINT / 3600
```

This is exact for UTC-aligned timestamps and matches the definition "number of 1-hour intervals elapsed since 1970-01-01T00:00:00Z". No timezone conversion is needed because `ts` is `TIMESTAMPTZ` stored in UTC.

_Alternative considered_: `DATE_PART('epoch', ts - '1970-01-01')::BIGINT / 3600` — equivalent but more verbose.

### D3: Three-step migration (nullable add → backfill → constraint)

PostgreSQL cannot add a `NOT NULL` column without a default in one step on a populated table. The migration sequence is:

1. `ALTER TABLE ohlcv ADD COLUMN tick_1h BIGINT` (nullable)
2. `UPDATE ohlcv SET tick_1h = EXTRACT(EPOCH FROM ts)::BIGINT / 3600 WHERE interval = '1h'`
3. `ALTER TABLE ohlcv ADD CONSTRAINT ohlcv_tick_1h_not_null CHECK (interval != '1h' OR tick_1h IS NOT NULL) NOT VALID; ALTER TABLE ohlcv VALIDATE CONSTRAINT ohlcv_tick_1h_not_null;`

Using `NOT VALID` + `VALIDATE` avoids a full table lock on validate — only a `SHARE UPDATE EXCLUSIVE` lock, which doesn't block concurrent reads/writes.

_Alternative considered_: `DEFAULT` value during `ADD COLUMN` — rejected because TimescaleDB hypertables handle backfills better via explicit `UPDATE`.

### D4: Writer passes `tick_1h` computed in Python

The writer builds tuples from `OHLCVRecord`. `tick_1h` is added as an optional field (default `None`) to `OHLCVRecord`, and the writer computes it at write time for 1h records:

```python
tick_1h = int(record.ts.timestamp()) // 3600 if record.interval == Interval.H1 else None
```

_Alternative considered_: Compute in SQL with a generated column — rejected because PostgreSQL generated columns cannot reference `EXTRACT(EPOCH ...)` deterministically in all TimescaleDB chunk scenarios, and Python-side computation keeps the logic testable.

## Risks / Trade-offs

- **Backfill scan on large table** → `UPDATE` on the full `ohlcv` hypertable for `interval = '1h'` rows could be slow. Mitigation: run migration during a low-traffic window; the hypertable's chunk structure limits lock scope per chunk.
- **CHECK constraint instead of NOT NULL** → `tick_1h` has no column-level NOT NULL; a missing `tick_1h` for non-1h rows is silently allowed. Mitigation: document the convention; enforce at the writer level.
- **Writer tuple count grows** → The INSERT column list and ON CONFLICT SET list must include `tick_1h`. Any out-of-band writers not updated will insert `NULL` for 1h rows, violating the constraint. Mitigation: the constraint will reject such rows at DB level.

## Migration Plan

1. Add new migration file `026_ohlcv_tick_1h.sql` following the existing numbered sequence.
2. Migration steps (in one transaction):
   - `ADD COLUMN tick_1h BIGINT`
   - `UPDATE` backfill for `interval = '1h'`
   - `ADD CONSTRAINT` with `NOT VALID`, then `VALIDATE CONSTRAINT`
3. Update `OHLCVRecord` to include optional `tick_1h: int | None`
4. Update `writer.py` to compute and pass `tick_1h` in the INSERT/upsert
5. Update `test_migrations.py` to assert `tick_1h` column exists and backfill is correct
6. Run full test suite

**Rollback**: Drop the constraint and column in a new migration. No data is lost.

## Open Questions

- None — scope is well-defined by the PRD.
