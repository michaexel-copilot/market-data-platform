-- Migration 030: Add is_aggregated flag to ohlcv table
--
-- Marks candles that were synthesised from a finer-grained interval
-- (e.g. 1h candles aggregated from 1m Binance data) rather than fetched
-- directly from a primary data source.
--
-- Semantics:
--   FALSE (default) — real candle from a primary source; always wins on upsert.
--   TRUE            — synthetic/aggregated candle; will be overwritten when a
--                     real candle for the same (instrument_id, interval, ts)
--                     is later ingested.

ALTER TABLE ohlcv ADD COLUMN IF NOT EXISTS
    is_aggregated BOOLEAN NOT NULL DEFAULT FALSE;
