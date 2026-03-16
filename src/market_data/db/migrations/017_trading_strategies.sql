-- 017_trading_strategies.sql
-- Persistent store for precomputed strategy indicator values

CREATE TABLE IF NOT EXISTS trading_strategies (
    instrument_id   VARCHAR      NOT NULL,
    strategy_name   VARCHAR      NOT NULL,
    indicator_name  VARCHAR      NOT NULL,
    indicator_value DOUBLE       NOT NULL,
    parameters      JSON,
    computed_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, strategy_name, indicator_name)
);
