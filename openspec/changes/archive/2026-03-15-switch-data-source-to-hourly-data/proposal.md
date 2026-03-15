## Why

The current data pipeline relies on Yahoo Finance for daily OHLCV data, which provides only ~1 candle per day resolution and CoinGecko's free API for fallback. A local EODHD service at `http://localhost:8010` is available that stores true hourly OHLCV data going back to 2020, enabling significantly more granular backtesting and chart analysis without depending on third-party rate limits.

## What Changes

- Replace Yahoo Finance (`yfinance`) as the primary OHLCV data source with the local EODHD service (`GET /v1/ohlcv/{symbol}?interval=1h`)
- Replace CoinGecko OHLCV price-history fetching with EODHD as well (CoinGecko ATH/ATL stats via `cg_market.py` are unaffected)
- Introduce a symbol-to-instrument-id mapping for the EODHD service (HL symbol → EODHD `instrument_id`, e.g. `BTC` → `bitcoin`)
- Update cache strategy for hourly candles (cache key changes from daily-granularity YF/CG keys to EODHD hourly keys)
- Downstream consumers (`web.py`, `draw_chart.py`, `perf_data.py`) receive hourly candles instead of daily; SMA and backtest logic must handle hourly granularity
- Remove `yfinance` dependency for price data (can be kept for non-price use-cases if any remain)

## Capabilities

### New Capabilities
- `eodhd-ohlcv-source`: Adapter that fetches and caches hourly OHLCV candles from the local EODHD service at `http://localhost:8010/v1/ohlcv/{symbol}`, handling pagination, timezone normalization, and symbol-to-instrument-id resolution

### Modified Capabilities
- `ohlcv-extended-history`: Requirements change from "fetch daily candles via Yahoo Finance from 2020-01-01" to "fetch hourly candles via EODHD service from 2020-01-01"; the cached candle format (fields, granularity) and cache-key scheme must be updated accordingly

## Impact

- **`draw_chart.py`**: `_fetch_from_yf()` and `_fetch_from_coingecko()` (price history) replaced by EODHD fetch; `YF_SYMBOL_MAP` and `CG_COIN_ID_MAP` replaced/supplemented by EODHD instrument-id map; K-token ×1000 multiplier logic must be preserved
- **`perf_data.py`**: `_fetch_5y_yf()`, `_fetch_5y_cg()`, `_fetch_hourly_yf()`, `_fetch_hourly_cg()` replaced; `fetch_5y_candles()` and `fetch_4h_candles()` sourced from EODHD (hourly candles available natively, 4H achieved by resampling)
- **`web.py`**: No interface changes expected; receives candles from existing `fetch_ohlcv()` / `fetch_5y_candles()` / `fetch_4h_candles()` wrappers
- **Cache**: Existing `cache/ohlcv/` files (YF/CG daily) become stale; new EODHD hourly cache files will be written alongside
- **Dependencies**: `yfinance` can be removed from `pyproject.toml` once migration is complete
- **Data quality note**: EODHD items with `volume: 0.0` are fill-forward artefacts and should be treated as missing volume (not zero-volume trades)
