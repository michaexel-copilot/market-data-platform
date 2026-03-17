-- 017_trading_strategies.sql
-- Persistent store for precomputed strategy indicator values

CREATE TABLE IF NOT EXISTS trading_strategies (
    instrument_id   TEXT            NOT NULL,
    strategy_name   TEXT            NOT NULL,
    indicator_name  TEXT            NOT NULL,
    indicator_value DOUBLE PRECISION NOT NULL,
    parameters      TEXT,
    computed_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, strategy_name, indicator_name)
);
