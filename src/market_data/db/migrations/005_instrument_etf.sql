-- 005_instrument_etf.sql
-- ETF-specific attributes

CREATE TABLE IF NOT EXISTS instrument_etf (
    instrument_id  VARCHAR NOT NULL PRIMARY KEY REFERENCES instruments(instrument_id),
    tracking_index VARCHAR,
    expense_ratio  DOUBLE,
    aum            DOUBLE,
    fund_type      VARCHAR CHECK (fund_type IN ('equity', 'fixed_income', 'commodity', 'mixed'))
);
