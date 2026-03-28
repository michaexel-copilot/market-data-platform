# improve-ohlcv-data-retrieval

Remove the interval dropdown from the "Update OHLCV Data" button in the asset detail pane.
Replace it with a smart, automatic multi-step update flow:

1. Check freshness of the most recent 1h candle for the selected instrument.
2. If the most recent 1h candle is older than 5 hours, trigger the `ohlcv_1h` ingestion job
   for that specific instrument.
3. After the 1h update, detect the gap between the most recent 1m candle and now.
4. If the instrument is crypto and Binance 1m data is available (per `ohlcv_data_available`),
   fetch missing 1m candles from Binance for the gap window.
5. Aggregate the fetched 1m candles into synthetic 1h candles (Python-side bucketing) and
   store them with `is_aggregated = TRUE` and `source = 'aggregated:binance_1m'`.
6. When real primary-source 1h candles later arrive (via scheduler or manual ingest), they
   overwrite the aggregated candles and reset `is_aggregated = FALSE`.

## Affected modules

- `src/market_data/db/migrations_pg/030_ohlcv_is_aggregated.sql` — new column
- `src/market_data/models/ohlcv.py` — `OHLCVRecord.is_aggregated` field
- `src/market_data/ingestion/writer.py` — upsert respects is_aggregated precedence
- `src/market_data/api/rest/admin.py` — new `POST /v1/admin/smart-update-ohlcv` endpoint
- `src/market_data/api/rest/console.py` — remove `DDL_OHLCV_PERIOD`, update button handler

## What changes

### Migration 030
Add `is_aggregated BOOLEAN NOT NULL DEFAULT FALSE` to the `ohlcv` table.  
Existing rows are real data and default to `FALSE`.

### OHLCVRecord model
Add `is_aggregated: bool = False` field.

### Writer upsert semantics
The ON CONFLICT…DO UPDATE clause is updated so that:
- **Real data** (`is_aggregated = FALSE`) always overwrites, including overwriting
  previously aggregated rows.
- **Aggregated data** (`is_aggregated = TRUE`) only writes to rows that are already
  aggregated (`ohlcv.is_aggregated = TRUE`) or are new inserts.  It never overwrites
  real primary-source candles.

### New endpoint — `POST /v1/admin/smart-update-ohlcv`
Request body: `{ "instrument_id": "<id>" }`

Step-by-step logic:
1. Query `MAX(ts)` for the instrument at `interval = '1h'`. If older than 5 hours (or no
   data exists) → run `_run_interval_job(Interval.ONE_HOUR, instrument_id=…)`.
2. Query `MAX(ts)` for the instrument at `interval = '1m'`. Compute gap = `(max_1m_ts, now)`.
3. Check `ohlcv_data_available JOIN data_source` for `has_1m = TRUE AND short_name = 'binance'`
   for this instrument. If not available, skip steps 4–5.
4. Call `BinanceConnector.fetch_ohlcv(instrument_id, Interval.ONE_MIN, since=max_1m_ts, until=now)`.
5. Aggregate 1m candles to 1h buckets Python-side:
   - open = first, high = max, low = min, close = last, volume = sum
   - `source = 'aggregated:binance_1m'`, `is_aggregated = True`
6. Upsert 1h aggregated candles via `write_ohlcv`.

Response:
```json
{
  "steps": [
    {"step": "1h_freshness_check", "status": "stale|fresh", "last_ts": "…", "threshold_hours": 5},
    {"step": "1h_ingest",          "status": "ok|skipped",  "written": 12},
    {"step": "1m_gap_check",       "status": "gap|no_gap",  "gap_hours": 3.5},
    {"step": "binance_availability","status": "available|unavailable"},
    {"step": "1m_fetch",           "status": "ok|skipped",  "fetched": 210},
    {"step": "1h_aggregation",     "status": "ok|skipped",  "written": 4}
  ],
  "total_written": 16
}
```

### Console changes
- Remove `#DDL_OHLCV_PERIOD` CSS block and `<select id="DDL_OHLCV_PERIOD">` element.
- Remove `ddlPeriod` JS reference and its `.disabled` line from `setActionsEnabled`.
- Update `BTN_UPDATE_OHLCV` click handler to:
  1. POST to `/v1/admin/smart-update-ohlcv` with `{instrument_id}`.
  2. Display per-step progress messages as the response arrives.
  3. Show a final summary (e.g. "1h data updated. Fetched 210 Binance 1m candles → 4
     synthetic 1h candles written.").
  4. Skip Binance steps gracefully for non-crypto or when Binance 1m is unavailable
     and note this in the message.

### README
Update the "Update OHLCV Data" description in the Management Console section and add a row
to the Admin endpoints table for `POST /v1/admin/smart-update-ohlcv`.

### Tests
- Unit test: `_aggregate_1m_to_1h` bucketing logic (open/high/low/close/volume correctness,
  midnight boundary, partial last bucket).
- Unit test: writer upsert — real data overwrites aggregated; aggregated does not overwrite real.
- Integration test: `POST /v1/admin/smart-update-ohlcv` with mocked Binance connector — verify
  step list, written counts, and `is_aggregated` flag on resulting rows.

## Step 1
[ ] /clear # clears the context window
[ ] /ospx-propose improve-ohlcv-data-retrieval

### Rückfragen KI (Claude Sonnet 4.6)
[ ] $rueckfragen von ki$

### Review
[ ] Review Proposal durchgeführt.
[ ] Alle Aspekte berücksichtigt

## Step 2
[ ] /ospx-apply

## Step 3 archive
[ ] /ospx-archive improve-ohlcv-data-retrieval
[ ] update documentation

## Step 4 Nacharbeiten
[ ] Review aller Tasks aus Step 0
- [ ] Migration 030 added, applied, and tested
- [ ] `is_aggregated` flag respected by writer (real overwrites aggregated, not vice versa)
- [ ] Interval dropdown removed from console
- [ ] Smart-update endpoint returns correct step list
- [ ] Non-crypto / Binance-unavailable path degrades gracefully with informative messages
- [ ] README updated (endpoint table + console description)
[ ] git commit mit passendem Kommentar # manuell

## Step 5 Definition of Done

[ ] Alle Workflow Schritte durchlaufen:
[ ] Review durchgeführt
[ ] git commit mit passendem Kommentar # manuell
[ ] Dokumentation aktualisiert
[ ] FAQ ergänzt
