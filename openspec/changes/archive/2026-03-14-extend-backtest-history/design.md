## Context

The Short Strategy Trades backtest in `draw_chart.py` fetches price data through two paths:

1. **Yahoo Finance** (`yfinance`) — used for most tokens via `_fetch_from_yf()`, currently hardcoded to `period="1y"` (~365 daily candles)
2. **CoinGecko free tier** — fallback for tokens not reliably listed on Yahoo (SUI, HYPE, TAO, MNT, UNI, CC, WLFI, etc.) via `_fetch_from_coingecko()`, currently using the `/coins/{id}/ohlc?days=365` endpoint

Investigation revealed three problems:

- **Limited history**: `period="1y"` caps all YF-backed tokens at ~365 candles regardless of how much data exists. The same yfinance call with `start="2020-01-01"` returns 2000–2265 candles for tokens that have existed since 2020.
- **Wrong ticker for UNI**: `UNI-USD` on Yahoo Finance resolves to "UNICORN Token" ($0.0002), not Uniswap ($3.91). The correct Yahoo Finance ticker is `UNI7083-USD`. `cg_market.py` already uses the correct CoinGecko ID (`uniswap`) for ATH/ATL, but `draw_chart.py` was charting the wrong asset entirely.
- **CoinGecko OHLC granularity degradation**: The `/ohlc?days=365` endpoint silently returns 4-day candles (not daily) for any request over 30 days. This means `days=365` yields only ~92 data points. An SMA-44 on 4-day candles covers ~176 calendar days, not 44 — making the strategy inconsistent between YF-backed and CG-backed tokens.

## Goals / Non-Goals

**Goals:**
- Extend backtest history to 2020-01-01 for all Yahoo Finance-backed tokens
- Fix UNI ticker so it charts Uniswap at the correct price
- Fix CoinGecko data path to return true daily candles, making SMA consistent across all tokens
- Keep the change minimal — no new dependencies, no UI changes, no changes to backtest logic

**Non-Goals:**
- Hourly data or intraday backtest (deferred; requires EODHD or Binance integration)
- Historical data for CoinGecko-backed tokens before their launch dates (data simply doesn't exist)
- Replacing Yahoo Finance or CoinGecko with a paid data provider (separate future change)
- Changing cache invalidation strategy (still per-day, per-ticker)

## Decisions

### Decision 1: Use `start="2020-01-01"` rather than `period="max"` for Yahoo Finance

**Chosen**: `yf.Ticker(sym).history(start="2020-01-01", interval="1d", auto_adjust=True)`

**Alternatives considered**:
- `period="max"` — would fetch all available data (some BTC data goes back to 2014), but pre-2020 crypto data is sparse, noisy, and pre-dates most HL-listed tokens. A fixed start date keeps all tokens on a comparable baseline.
- `period="5y"` — convenient but already in use for the Performance tab's `fetch_5y_candles()`, and would give ~2021 start not 2020.

**Rationale**: 2020-01-01 is a clean baseline that pre-dates most meaningful token price action while avoiding the noise of the 2017–2019 era. Tokens launched after 2020 naturally start from their listing date.

### Decision 2: Replace CoinGecko `/ohlc` with `/market_chart` for daily candles

**Chosen**: `GET /coins/{id}/market_chart?vs_currency=usd&days=2000&interval=daily`

**Alternatives considered**:
- Keep `/ohlc?days=365` — status quo, but returns 4-day candles (92 points), not daily. SMA is meaningless at that granularity.
- `/ohlc?days=30` — would return daily candles but only 30 days of history. Unusable for a 44-day SMA.
- CoinGecko Pro `days=max` — returns full history as daily candles, but requires a paid API key (401 on free tier). Out of scope for this change.
- Binance public API — free, excellent coverage, daily candles since listing. Valid alternative but adds a new dependency and a new fetch path. Deferred to a future change.

**Rationale**: The `/market_chart` endpoint with `?interval=daily` returns one data point per day for ranges > 90 days on the free tier. `days=2000` covers from 2020 to today. The response format (`{"prices": [[ts_ms, price], ...]}`) gives close prices only — no OHLC. Since the backtest only uses `close` values (and high/low only for chart rendering), close-only data is acceptable for CG-fallback tokens.

**Trade-off**: CG market_chart returns `[timestamp, price]` pairs (close only), not full OHLC. For CG-backed tokens the chart will render without high/low wicks. This is already the case for some tokens due to how CoinGecko's OHLC data was sparsely populated.

### Decision 3: Add UNI to `CG_COIN_ID_MAP`, not `YF_SYMBOL_MAP`

**Chosen**: Add `"UNI": "uniswap"` to `CG_COIN_ID_MAP` in `draw_chart.py`

**Alternatives considered**:
- Add `"UNI": "UNI7083-USD"` to `YF_SYMBOL_MAP` — this would work (UNI7083-USD is confirmed correct, data from Sep 2020 to today at correct prices). However, the disambiguated ticker format (`UNI7083-USD`) is fragile — Yahoo Finance has been known to renumber or change these IDs.
- Do both (YF primary, CG fallback) — over-engineering for one token.

**Rationale**: CoinGecko's `uniswap` ID is stable and canonical. The CG market_chart path now returns proper daily candles (per Decision 2), so this is no longer a downgrade. Avoids relying on a numeric-suffix YF ticker that could silently break.

## Risks / Trade-offs

- **CG rate limiting on first run**: With ~30 CG-fallback tokens, fetching extended history on first run will hit the free tier rate limit (~30 req/min). The existing cache-per-day strategy means this only happens once. Mitigation: add a small `time.sleep(2)` between CG requests if batch-fetching, or rely on the fact that users open tokens one at a time via the web UI.
- **Cache file size**: Extended history files are ~6× larger (~2000 candles vs ~365). At ~200 bytes/candle JSON, that's ~400 KB per token. For 150+ tokens, ~60 MB total on disk. Acceptable.
- **CG market_chart close-only**: Chart rendering for CG-backed tokens won't have high/low wicks. This is a known visual limitation, not a strategy correctness issue.
- **YF ticker rot**: `UNI7083-USD` was manually discovered. There may be other tokens with similar wrong mappings not yet identified. Out of scope for this change — UNI is the only confirmed case.

## Migration Plan

1. Clear stale OHLCV cache entries (optional — old `_365` data is naturally replaced on first access since cache keys are date-stamped by today)
2. Deploy code changes to `draw_chart.py`  
3. On first web request per token, extended history is fetched and cached
4. No database migrations, no rollback needed — cache files are disposable

## Open Questions

- Should `fetch_5y_candles()` in `perf_data.py` also be aligned to `start="2020-01-01"` for consistency, or left on `period="5y"`? (Currently out of scope — Performance tab is separate.)
- Are there other Yahoo Finance tickers with the same numeric-suffix disambiguation problem? A one-time audit of all ~150 HL symbols against current YF prices would be worthwhile before implementing.
