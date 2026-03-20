## Context

The scheduler runs `_run_interval_job` once per interval (1m, 5m, 1h, 1d). For every
`(connector, instrument_id)` pair it calls `conn.fetch_ohlcv()` which uses
`resp.raise_for_status()`, raising `httpx.HTTPStatusError` on non-2xx responses.
The existing error handler in `jobs.py` gives 403 and 429 special treatment but lets
all other HTTP errors (including 404) fall through to a generic `logger.warning`.
Assets absent from a data source (e.g., `home3` on eodhd) therefore generate a 404 on
every scheduler run, indefinitely.

Relevant code path:
```
scheduler → _run_interval_job(interval)
              → for conn in registry.by_interval(interval)
                  → for instrument_id in _active_instrument_ids()
                      → conn.fetch_ohlcv(...)          # raises HTTPStatusError on 404
                          → except httpx.HTTPStatusError  # only 403/429 handled
```

## Goals / Non-Goals

**Goals:**
- Persist each unique `(instrument_id, data_source, interval)` 404 event with URL and timestamp.
- Suppress future fetches for any flagged `(instrument_id, data_source, interval)` combination.
- Keep the DB query overhead O(1) per job run, not O(N) per instrument.

**Non-Goals:**
- Automatic expiry or re-enable of suppressed entries.
- Management-console UI for viewing or clearing suppressed entries.
- Handling other 4xx codes (403 and 429 are already handled separately).
- Rate-limiting or exponential back-off for 404s (not useful — 404 is permanent).

## Decisions

### 1. Table name and primary key

**Decision**: New table `asset_not_found` with a unique constraint on
`(instrument_id, data_source, interval)`. `INSERT … ON CONFLICT DO UPDATE SET
last_seen_at = NOW()` so repeated hits update the timestamp without duplicates.

Columns:
```sql
instrument_id  TEXT         NOT NULL
data_source    TEXT         NOT NULL   -- conn.name
interval       TEXT         NOT NULL   -- '1m', '5m', '1h', '1d'
url            TEXT         NOT NULL   -- exc.response.request.url (first occurrence)
first_seen_at  TIMESTAMPTZ  NOT NULL   DEFAULT NOW()
last_seen_at   TIMESTAMPTZ  NOT NULL   DEFAULT NOW()
PRIMARY KEY (instrument_id, data_source, interval)
```

*Alternative considered*: surrogate `SERIAL` primary key. Rejected — the composite
natural key is the identity; a surrogate adds nothing.

### 2. Suppression granularity

**Decision**: Suppress at `(instrument_id, data_source, interval)`. An asset may be
available on source A but not on source B, or available for 1h but not 1d on the same
source.

*Alternative considered*: suppress per `(instrument_id, data_source)` across all
intervals. Rejected — too coarse; e.g., eodhd may serve daily data but not intraday
for the same ticker.

### 3. Pre-fetch check strategy

**Decision**: At the start of each `_run_interval_job` call, load all blocked combos
for that interval into a `frozenset[tuple[str, str]]` (instrument_id, data_source).
The inner loop does an O(1) set-member test before each fetch.

*Alternative considered*: Per-combination synchronous DB query inside the loop.
Rejected — the loop iterates O(connectors × instruments); individual queries add
unnecessary latency to the async event loop.

### 4. `data_source` identifier

**Decision**: Use `conn.name` — already used for logging and is the stable public
name of each connector. Stored as-is; renaming a connector only affects new records.

### 5. URL storage

**Decision**: Store `str(exc.response.request.url)` from the first 404 occurrence.
Subsequent 404s do not overwrite the URL (only `last_seen_at` is updated via
ON CONFLICT). This preserves the original context for debugging.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Transient 404 (server glitch) permanently suppresses a valid asset | Record is trivially removable with `DELETE FROM asset_not_found WHERE …` |
| `conn.name` collides if two connectors share a name | Not currently possible; connector names are unique strings in the registry |
| Job-start bulk load holds stale data for the duration of a run | Acceptable — a newly recorded block takes effect on the next run, not mid-run |

## Migration Plan

1. Add migration `028_asset_not_found.sql` — `CREATE TABLE asset_not_found (…)`.
2. No data migration needed.
3. Add DB helper module `src/market_data/db/asset_not_found.py` with:
   - `record_not_found(conn, instrument_id, data_source, interval, url)` — upsert
   - `load_blocked(conn, interval) → frozenset[tuple[str, str]]` — bulk read
4. Update `_run_interval_job` in `jobs.py`:
   - Call `load_blocked` once before the inner loops.
   - Skip fetch when `(instrument_id, conn.name)` is in the blocked set.
   - Catch `status_code == 404` before the generic fallthrough; call `record_not_found`.
5. Rollback: `DROP TABLE asset_not_found;` and revert `jobs.py`.

## Open Questions

- Should clearing a suppressed entry also trigger an immediate re-fetch, or wait for
  the next scheduled run? (Current design: wait for next run — simpler.)
