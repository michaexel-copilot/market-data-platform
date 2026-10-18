-- Read-only views over the existing ohlcv hypertable for ohlcv_backfill.py.
-- Only creates/replaces these two views; never touches ohlcv itself.

-- Depth, fill ratio and staleness per series (replaces the manual Excel overview).
CREATE OR REPLACE VIEW backfill_coverage AS
SELECT instrument_id, interval, source,
       min(ts)  AS first_ts,
       max(ts)  AS last_ts,
       count(*) AS rows,
       round((count(*) / (extract(epoch FROM max(ts) - min(ts))
             / CASE interval WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '1h' THEN 3600 ELSE 86400 END
             + 1))::numeric, 3) AS fill_ratio,
       now() - max(ts) AS lag
FROM ohlcv
GROUP BY instrument_id, interval, source;

-- Every hole inside a series (gap between consecutive candles > 1 interval),
-- across all sources since ohlcv holds one candle per (instrument_id, interval, ts).
-- Full scan: filter by instrument_id/interval when querying.
CREATE OR REPLACE VIEW backfill_gaps AS
SELECT instrument_id, interval, prev_ts AS gap_after, ts AS gap_before, ts - prev_ts AS gap
FROM (
    SELECT instrument_id, interval, ts,
           lag(ts) OVER (PARTITION BY instrument_id, interval ORDER BY ts) AS prev_ts
    FROM ohlcv
) s
WHERE prev_ts IS NOT NULL
  AND ts - prev_ts > CASE interval WHEN '1m' THEN INTERVAL '1 minute' WHEN '5m' THEN INTERVAL '5 minutes'
                                   WHEN '1h' THEN INTERVAL '1 hour' ELSE INTERVAL '1 day' END;
