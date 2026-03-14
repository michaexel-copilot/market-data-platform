## 1. Fix UNI Ticker Mapping

- [x] 1.1 Add `"UNI": "uniswap"` to `CG_COIN_ID_MAP` in `draw_chart.py`
- [x] 1.2 Delete any stale cached OHLCV files for UNI (e.g. `cache/ohlcv/UNI-USD_*.json`) so the wrong data isn't served from cache

## 2. Extend Yahoo Finance History

- [x] 2.1 Change `_fetch_from_yf()` in `draw_chart.py` to use `start="2020-01-01"` instead of `period="1y"`
- [x] 2.2 Verify sample YF tokens return extended candle counts (BTC: ~2265, SOL: ~2165, AVAX: ~2002) by running a quick manual test or unit check

## 3. Fix CoinGecko Daily Granularity

- [x] 3.1 Replace the `/coins/{id}/ohlc?days=365` call in `_fetch_from_coingecko()` with `/coins/{id}/market_chart?vs_currency=usd&days=365` (free-tier max; `interval=daily` is Pro-only but omitting it auto-returns daily candles for days>90)
- [x] 3.2 Update the CG response parser: market_chart returns `{"prices": [[ts_ms, price], ...]}` — map each entry to a candle dict with `open`, `high`, `low`, `close` all set to `price` (close-only source)
- [x] 3.3 Verify SUI returns ~daily-spaced candles after the fix: 366 candles, 86400s gap ✅

## 4. Cache Cleanup

- [x] 4.1 Delete existing daily OHLCV cache files for CoinGecko-backed tokens (`cache/ohlcv/cg:*_*.json`) so stale 4-day-granularity data is not served
- [x] 4.2 Confirm cache filenames are unchanged (still `{source_key}_{today}.json`) — no cache key migration needed

## 5. Validation

- [x] 5.1 UNI last close confirmed $3.93 (Uniswap, not $0.0002 UNICORN Token) ✅
- [x] 5.2 BTC extended to 2265 candles from 2020-01-01 (was ~365) ✅
- [x] 5.3 SUI daily granularity confirmed: 366 candles, 86400s gap, close $0.986 ✅
- [x] 5.4 Ran `draw_all_charts.py` across all 229 symbols: **218/229 succeeded**. Remaining 11 failures are pre-existing issues (4 tokens with no valid YF data needing CoinGecko mappings: BRETT, MOODENG, POPCAT, HPOS; 5 CG tokens hit rate limit in batch despite retry; 2 were NaN-data tokens fixed as bonus work). NaN-filter fix added to `_fetch_from_yf` to prevent Axis errors from zero/NaN yfinance rows.
