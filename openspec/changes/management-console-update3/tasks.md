## 1. DB Migrations

- [x] 1.1 Create `015_ohlcv_data_available.sql` — new table `ohlcv_data_available (instrument_id, data_source_id, has_1m, has_5m, has_1h, has_1d)` with PK `(instrument_id, data_source_id)`
- [x] 1.2 Create `016_eodhd_data_source.sql` — seed eodhd row in `data_source` (id=2, priority=1) and seed `ohlcv_data_available` rows for all existing crypto instruments (eodhd: all true; cmc: has_1d only)

## 2. API

- [x] 2.1 Add `GET /v1/instruments/{symbol}/ohlcv-availability` to `instruments.py` — query `ohlcv` + views, return first/last per interval; omit intervals with no data
- [x] 2.2 Add `GET /v1/instruments/{symbol}/ohlcv-data-available` to `instruments.py` — join `ohlcv_data_available` with `data_source`, return matrix keyed by source short_name

## 3. Console

- [x] 3.1 After the fundamentals key-value table, fetch and render an "OHLCV Time Range" section using the new `/ohlcv-availability` endpoint (table: Interval / First / Last; fall back to "No OHLCV data available")
- [x] 3.2 After the OHLCV Time Range section, fetch and render an "OHLCV Data Available" matrix using the new `/ohlcv-data-available` endpoint (rows: 1m/5m/1h/1d; columns: data source short names; cells: ✓ or —)
- [x] 3.3 Add CSS for the two new sections (compact table styling consistent with existing fundamentals table)
