## Context

The "Update OHLCV Data" button currently delegates entirely to the cache import pathway:
the user picks an interval from `DDL_OHLCV_PERIOD` and the console calls
`POST /v1/admin/import-ohlcv-cache` with that interval. This works well for bulk historical
back-fills from a local cache but cannot fill intraday gaps that are not yet on disk and
requires domain knowledge from the operator (which interval is stale? which source covers it?).

The scheduler already handles continuous ingest, but when it is paused or when a gap forms
(e.g. the process was restarted, an API was briefly rate-limited), reaching for the console
button is the natural next step. The new flow should do the right thing without the operator
needing to understand the interval matrix.

## Goals / Non-Goals

**Goals:**
- One click does the sensible thing: check freshness, ingest if stale, fill any intraday gap
  from Binance's free public API.
- The `ohlcv` table tracks which candles are synthetic so real data can win on conflict.
- The console gives actionable per-step feedback instead of a single opaque "rows imported"
  count.

**Non-Goals:**
- This does not replace the scheduler — it is a manual on-demand action only.
- Gap fill is Binance-only (crypto). Non-crypto instruments get steps 1–2 only.
- The existing `POST /v1/admin/import-ohlcv-cache` endpoint is unchanged; any tooling that
  calls it directly continues to work.
- No backfill of `is_aggregated` on pre-existing rows (all default to `FALSE` = real data,
  which is correct).

## Decisions

### Decision: Add `is_aggregated` column to `ohlcv` vs. a separate table

**Chosen**: Column on `ohlcv`.

**Why**: A separate table (e.g. `ohlcv_aggregated`) would require a `UNION` or an additional
JOIN on every read path, increase query complexity, and complicate the TimescaleDB hypertable
setup. A single nullable boolean column with a default of `FALSE` is transparent to all
existing callers and adds negligible storage overhead.

**Alternative considered**: A separate `source` prefix convention (e.g. `source LIKE
'aggregated:%'`) without a dedicated boolean. Rejected because pattern-matching on a `TEXT`
column in the conflict-resolution `CASE WHEN` clause is slower and less readable than a
boolean predicate.

### Decision: Conflict-resolution semantics — CASE WHEN in SQL vs. application-level guard

**Chosen**: `CASE WHEN excluded.is_aggregated = FALSE OR ohlcv.is_aggregated = TRUE` guard
inside the `ON CONFLICT DO UPDATE SET` clause.

**Why**: A single upsert statement remains atomic and safe for concurrent writes. The writer
does not need to pre-read existing rows (no SELECT before INSERT), which avoids a TOCTOU race
and keeps the write path O(1) per record.

**Alternative considered**: Read existing `is_aggregated` flag before deciding to write.
Rejected for the race condition and added I/O cost.

### Decision: Binance 1m aggregation is done Python-side vs. PostgreSQL-side

**Chosen**: Python dict bucketing by truncated-to-hour timestamp.

**Why**: The aggregation input is already in memory (freshly fetched records). Pushing it to
PostgreSQL would require a temporary table or a complex multi-step INSERT…SELECT, adding
round-trips. The Python path is simpler, testable in isolation, and sufficient for the
expected record count (at most ~300 candles for a 5-hour gap).

### Decision: New endpoint `POST /v1/admin/smart-update-ohlcv` vs. extending `run-ingest`

**Chosen**: New dedicated endpoint.

**Why**: The smart-update flow combines freshness checking, conditional ingest, Binance
fetching, and aggregation — it is not a variant of the generic `_run_interval_job` loop.
A separate endpoint has a clean, single-purpose contract and is easier to test and document.
`run-ingest` remains unchanged for programmatic callers.

## Risks / Trade-offs

- **Binance symbol mapping**: `BinanceConnector.fetch_ohlcv` strips `-`/`/` from
  `instrument_id` to form the Binance symbol (e.g. `BTC-USD` → `BTCUSD`). If the
  stored `instrument_id` does not map to a valid Binance pair, the fetch returns an
  empty list (HTTP error → `break`) and step `1m_fetch` reports `fetched: 0`.
  → *Mitigation*: The `binance_availability` step gates the fetch on
  `ohlcv_data_available.has_1m = TRUE AND short_name = 'binance'`; operators who have
  populated this table for their instruments will get a reliable result.

- **Partial last 1h bucket**: If the gap fill runs at 14:42 UTC, the current 1h bucket
  (14:00–14:42) will produce a synthetic candle with only 42 minutes of 1m data.
  When the scheduler later ingests the real 14:00 1h candle it will overwrite this partial
  synthetic candle — the correct outcome.

- **Hypertable `ALTER TABLE` on migration 030**: `ADD COLUMN … DEFAULT FALSE` on a
  TimescaleDB hypertable is generally fast (metadata-only in PostgreSQL 11+), but it
  requires an `ACCESS EXCLUSIVE` lock. On highly-loaded systems this should be run during
  a low-traffic window.
  → *Mitigation*: Standard migration procedure; `uv run migrate` should be run after
  stopping the scheduler.

## Migration Plan

1. Stop the scheduler (`uv run scheduler` process or disable all jobs via the Scheduler tab).
2. Run `uv run migrate` — this applies migration 030 (`ALTER TABLE ohlcv ADD COLUMN
   is_aggregated BOOLEAN NOT NULL DEFAULT FALSE`).
3. Deploy the updated code (new endpoint, writer, model, console).
4. Re-enable the scheduler.
5. **Rollback**: Revert code, then `ALTER TABLE ohlcv DROP COLUMN is_aggregated` (no data
   loss; the column contains only defaults or synthetic flags).

## Open Questions

- Should the smart-update also populate `1m` data from Binance for its own sake (not just
  as an aggregation source), so that the OHLCV time-range table shows accurate 1m coverage?
  Currently the fetched 1m records are not written; only the aggregated 1h candles are
  persisted. → *Decision deferred; the 1m write can be added later without schema changes.*
