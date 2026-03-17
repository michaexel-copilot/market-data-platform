-- 005_instrument_etf.sql
-- ETF-specific attributes

CREATE TABLE IF NOT EXISTS instrument_etf (
    instrument_id  TEXT            NOT NULL PRIMARY KEY REFERENCES instruments(instrument_id),
    tracking_index TEXT,
    expense_ratio  DOUBLE PRECISION,
    aum            DOUBLE PRECISION,
    fund_type      TEXT CHECK (fund_type IN ('equity', 'fixed_income', 'commodity', 'mixed'))
);
