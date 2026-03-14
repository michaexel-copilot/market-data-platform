## Why

The Short Strategy Trades backtest is currently limited to the last 12 months of daily data, which produces too few trades for statistical confidence. Extending to 2020-01-01 gives ~4–6× more historical trades at no extra complexity. During investigation we also discovered two data quality bugs affecting chart correctness right now: `UNI-USD` on Yahoo Finance maps to "UNICORN Token" (not Uniswap), and CoinGecko's OHLC endpoint silently degrades to 4-day candles for any request over 30 days, making SMA values inconsistent across token groups.

## What Changes

- Change `_fetch_from_yf()` to use `start="2020-01-01"` instead of `period="1y"` so all Yahoo Finance-backed tokens get their full available history
- Add `"UNI": "UNI7083-USD"` to `YF_SYMBOL_MAP` in `draw_chart.py` to fix the wrong ticker mapping (Uniswap, not UNICORN Token)
- Replace the CoinGecko OHLC endpoint (`/coins/{id}/ohlc`) with the market_chart endpoint (`/coins/{id}/market_chart`) for CG-fallback tokens, which returns true daily candles instead of 4-day aggregates
- Cache key and cache filename format must accommodate the extended date range (currently always named by today's date — cache invalidation strategy stays the same, but the fetched data now spans from 2020)
- The SMA period spinner UI and backtest logic remain unchanged — they operate on whatever candles are available, longer history just means more trades computed

## Capabilities

### New Capabilities

- `ohlcv-extended-history`: Fetching and caching daily OHLCV data from a configurable start date (default 2020-01-01) rather than a rolling 1-year window. Covers both Yahoo Finance and CoinGecko data paths.

### Modified Capabilities

<!-- No existing spec files — openspec/specs/ is empty -->

## Impact

- **`draw_chart.py`**: `_fetch_from_yf()` date range change; `YF_SYMBOL_MAP` UNI fix; `_fetch_from_coingecko()` endpoint swap
- **`perf_data.py`**: `fetch_5y_candles()` already uses `period="5y"` — verify it is unaffected or align it to the same start-date approach
- **Cache**: Existing daily cache files (named `{ticker}_{today}.json`) remain valid; first run after the change fetches and stores the full extended history (~2000 candles vs ~365 today) — slightly larger files, one-time slower fetch per token
- **Backtest compute**: More candles = more trades computed per request; should remain fast (pure Python loop over ~2000 items)
- **No new dependencies**: yfinance and requests already in use
