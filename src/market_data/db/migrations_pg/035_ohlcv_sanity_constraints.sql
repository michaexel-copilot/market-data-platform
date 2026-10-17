-- Migration 035: Remove impossible OHLCV rows and prevent them from being reinserted

SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0;

DELETE FROM ohlcv
WHERE open <= 0
   OR high <= 0
   OR low <= 0
   OR close <= 0
   OR high < GREATEST(open, close)
   OR low > LEAST(open, close)
   OR low > high
   OR (volume IS NOT NULL AND volume < 0)
   OR (vwap IS NOT NULL AND vwap < 0)
   OR (trade_count IS NOT NULL AND trade_count < 0)
   OR (market_cap IS NOT NULL AND market_cap < 0);

ALTER TABLE ohlcv DROP CONSTRAINT IF EXISTS ohlcv_price_sanity;

ALTER TABLE ohlcv
    ADD CONSTRAINT ohlcv_price_sanity
    CHECK (
        open > 0
        AND high > 0
        AND low > 0
        AND close > 0
        AND high >= GREATEST(open, close)
        AND low <= LEAST(open, close)
        AND low <= high
        AND (volume IS NULL OR volume >= 0)
        AND (vwap IS NULL OR vwap >= 0)
        AND (trade_count IS NULL OR trade_count >= 0)
        AND (market_cap IS NULL OR market_cap >= 0)
    );

RESET timescaledb.max_tuples_decompressed_per_dml_transaction;