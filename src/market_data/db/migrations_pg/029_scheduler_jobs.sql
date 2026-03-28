-- 029: scheduler job enable/disable table
CREATE TABLE IF NOT EXISTS scheduler_jobs (
    job_id      TEXT        PRIMARY KEY,
    enabled     BOOL        NOT NULL DEFAULT true,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed all known jobs; do nothing if they already exist so re-runs are safe.
INSERT INTO scheduler_jobs (job_id) VALUES
    ('ohlcv_1m'),
    ('ohlcv_5m'),
    ('ohlcv_1h'),
    ('ohlcv_1d')
ON CONFLICT DO NOTHING;
