## Why

The "Update OHLCV Data" button in the asset detail pane requires the user to manually
select an interval from a dropdown before triggering a cache import. This is error-prone,
requires domain knowledge about which intervals are stale, and cannot fill intraday gaps
that the local cache doesn't cover. Automating the decision and adding a Binance 1m
gap-fill layer closes intraday data holes that currently require manual scheduler
intervention.

## What Changes

- Remove the `DDL_OHLCV_PERIOD` interval dropdown from the asset detail action bar.
- Replace the cache-import call with a new `POST /v1/admin/smart-update-ohlcv` endpoint
  that runs a deterministic multi-step update sequence automatically:
  1. Check freshness of 1h candles (threshold: 5 hours).
  2. If stale, trigger the `ohlcv_1h` ingestion job for the instrument.
  3. Detect the gap between the most recent 1m candle and now.
  4. If Binance 1m data is available for the instrument, fetch the gap range and
     aggregate 1m → 1h synthetic candles.
- Add `is_aggregated BOOLEAN NOT NULL DEFAULT FALSE` to the `ohlcv` table (migration 030)
  to distinguish synthetic candles from primary-source candles.
- Update the writer upsert so real candles always overwrite synthetic ones, but synthetic
  candles never overwrite real candles.
- Show per-step progress feedback in the console (freshness result, rows ingested, Binance
  candles fetched, synthetic 1h candles written).

## Capabilities

### New Capabilities

- `smart-ohlcv-update`: Fully automated multi-step OHLCV update for a single instrument —
  freshness check, 1h ingest trigger, Binance 1m gap fill, 1m→1h aggregation, and
  is_aggregated-aware upsert. Exposed as `POST /v1/admin/smart-update-ohlcv`.

### Modified Capabilities

- `time-series-ohlcv`: Schema change — adds `is_aggregated` column to the `ohlcv` table;
  upsert semantics updated so real candles take precedence over aggregated ones.
- `management-console`: `DDL_OHLCV_PERIOD` dropdown removed from the action bar; the
  "Update OHLCV Data" button handler is replaced with the smart-update flow including
  per-step status messages.

## Impact

- **Database**: Migration 030 alters the `ohlcv` hypertable — requires `uv run migrate`
  after deployment.
- **API**: New admin endpoint `POST /v1/admin/smart-update-ohlcv`; existing
  `POST /v1/admin/import-ohlcv-cache` is unchanged (still callable directly).
- **Writer**: `write_ohlcv` gains `is_aggregated`-aware conflict resolution; all existing
  callers are unaffected because the new field defaults to `False`.
- **Model**: `OHLCVRecord.is_aggregated` field added with default `False`; no breaking
  change to existing producers.
- **Console**: UI change only — the interval dropdown is removed; no other pane is
  affected.
- **Connectors**: `BinanceConnector.fetch_ohlcv` called at request time (not in scheduler
  loop); no scheduler changes.
