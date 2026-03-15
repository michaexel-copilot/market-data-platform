## 1. Symbol Mapping & Source Routing (draw_chart.py)

- [x] 1.1 Add `EODHD_BASE_URL = "http://localhost:8010"` constant and `EODHD_SYMBOL_MAP` dict mapping HL symbols to EODHD instrument IDs (BTC→bitcoin, ETH→ethereum, ADA→cardano, ALGO→algorand, SKY→sky)
- [x] 1.2 Update `resolve_source_key()` to check `EODHD_SYMBOL_MAP` first and return `eodhd:{instrument_id}` with appropriate multiplier when a match is found
- [x] 1.3 Update `get_data_source()` to return `"EODHD"` when source_key starts with `"eodhd:"`

## 2. EODHD Fetch Adapter (draw_chart.py)

- [x] 2.1 Implement `_fetch_eodhd_hourly_raw(instrument_id: str) -> list[dict]` that paginates through all pages of `GET /v1/ohlcv/{instrument_id}?interval=1h&page_size=1000`, normalizes timestamps to UTC, and treats `volume=0.0` as `None`
- [x] 2.2 Implement `_resample_hourly_to_daily(hourly: list[dict]) -> list[dict]` that buckets by UTC calendar date (open=first, high=max, low=min, close=last, volume=sum of non-None) and returns sorted daily candles
- [x] 2.3 Add EODHD-specific cache helpers: `_eodhd_cache_path(instrument_id)` returning `cache/ohlcv/{instrument_id}_eodhd_1h_{YYYY-MM-DD}.json`, `_load_eodhd_cache(instrument_id)`, `_save_eodhd_cache(instrument_id, hourly_candles)`

## 3. Wire EODHD into fetch_ohlcv (draw_chart.py)

- [x] 3.1 Update `fetch_ohlcv()` to handle `eodhd:` source keys: load from EODHD hourly cache (or fetch+save), then resample to daily using `_resample_hourly_to_daily()`

## 4. Wire EODHD into perf_data.py

- [x] 4.1 Import `EODHD_SYMBOL_MAP`, `_fetch_eodhd_hourly_raw`, `_load_eodhd_cache`, `_save_eodhd_cache`, `_resample_hourly_to_daily` from `draw_chart` in `perf_data.py`
- [x] 4.2 Update `fetch_5y_candles()` to dispatch to EODHD path when `source_key` starts with `"eodhd:"`: use the EODHD hourly cache and resample to daily
- [x] 4.3 Update `fetch_4h_candles()` to dispatch to EODHD path when `source_key` starts with `"eodhd:"`: use the EODHD hourly cache and resample to 4H (or return raw hourly for `resolution="1h"`)
