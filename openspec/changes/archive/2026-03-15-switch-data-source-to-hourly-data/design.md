## Context

The application fetches OHLCV price data for ~229 Hyperliquid perpetual symbols from two external third-party APIs:
- **Yahoo Finance** (`yfinance` library): daily candles from 2020-01-01, with true H/L range. Rate limits are informal/unofficial.
- **CoinGecko** free tier: daily candles for up to 365 days (close-only, no real H/L), or hourly for 90 days. Rate-limited to ~5 req/min.

A **local EODHD service** (`http://localhost:8010`) is now available that stores true hourly OHLCV data sourced from EODHD. It runs entirely offline with no rate limits. As of March 2026 it has hourly data for **5 symbols** (bitcoin, ethereum, cardano, algorand, sky) going back to October 2020, with more symbols expected over time as data is imported.

The app's routing logic in `draw_chart.py` uses `resolve_source_key()` to dispatch fetches to YF or CG. `perf_data.py` has its own parallel fetch layer for 5Y daily and 4H/1H candles.

## Goals / Non-Goals

**Goals:**
- Route OHLCV fetches through the local EODHD service for symbols it covers
- Yield true hourly H/L data for EODHD-covered symbols (vs. CG close-only)
- Eliminate external API calls for EODHD-covered symbols (no rate limits, no network dependency)
- Maintain existing public function signatures (`fetch_ohlcv`, `fetch_5y_candles`, `fetch_4h_candles`) — no breaking changes to callers
- Be easily extensible as more symbols are imported into EODHD

**Non-Goals:**
- Replacing YF/CG for symbols not yet in EODHD — they continue using YF/CG as before
- Changing chart SMA periods or backtest logic to hourly granularity — `fetch_ohlcv` continues returning daily candles (by resampling EODHD hourly → daily)
- Importing missing symbols into EODHD (out of scope — done externally)
- Removing `yfinance` dependency (will remain for uncovered symbols)

## Decisions

### Decision 1: New `eodhd:` source-key prefix

**Choice**: Extend `resolve_source_key()` to return `eodhd:{instrument_id}` for EODHD-covered symbols (e.g. `eodhd:bitcoin`) alongside the existing `yf:SOL-USD` and `cg:hyperliquid` routing.

**Rationale**: The prefix pattern is already established in `draw_chart.py` (`cg:` vs YF ticker). Adding `eodhd:` keeps the dispatch logic consistent without changing function signatures. The EODHD `instrument_id` closely mirrors CoinGecko IDs (same names: `bitcoin`, `ethereum`, `cardano`), so the mapping is trivially derived from `CG_COIN_ID_MAP` where the IDs overlap.

**Alternative considered**: Separate `EODHD_SYMBOL_MAP` dict independent of CG. Rejected because the IDs are mostly the same, so a simple override map suffices.

### Decision 2: EODHD hourly → daily resample in `fetch_ohlcv` and `fetch_5y_candles`

**Choice**: Fetch all EODHD hourly candles and resample them to 1-day buckets before returning from `fetch_ohlcv()` and `fetch_5y_candles()`. `fetch_4h_candles(resolution="1h")` and `fetch_4h_candles(resolution="4h")` return native hourly / 4H-resampled candles respectively.

**Rationale**: All downstream consumers (`prepare_chart_data`, `backtest_short_strategy`, `compute_perf_rows`) are calibrated for daily candles — SMA periods, performance windows, and chart tick density all assume ~1 candle/day. Returning hourly candles would require widespread changes to SMA periods, backtesting, and chart rendering. The existing daily interface is a stable abstraction; EODHD hourly data becomes a better-quality *source* for daily candles (real H/L vs. CG close-only), not a new interface contract.

**Alternative considered**: Expose hourly candles directly from `fetch_ohlcv()`. Rejected because it would require updating SMA periods (~24×), backtest logic, and chart rendering across multiple files.

### Decision 3: Single unified EODHD hourly cache per symbol

**Choice**: Cache the full raw hourly candle list from EODHD (all pages) as `cache/ohlcv/{instrument_id}_eodhd_1h_{YYYY-MM-DD}.json`. All three consumer functions (`fetch_ohlcv`, `fetch_5y_candles`, `fetch_4h_candles`) read from this same hourly cache and resample in-memory to their required resolution.

**Rationale**: Avoids fetching the same EODHD paginated data multiple times per day for different resolutions. A single hourly cache of ~46k candles is ~5-10 MB per symbol — acceptable. Resampling in memory is cheap.

**Alternative considered**: Separate cache files per resolution (daily, 4h, 1h). Rejected as redundant — each would require a separate EODHD fetch pass.

### Decision 4: Zero-volume EODHD candles treated as missing volume

**Choice**: EODHD candles with `volume: 0.0` are treated as `None` (missing) rather than genuinely zero-volume.

**Rationale**: EODHD uses volume=0 as a fill-forward artefact for intervals with no real trade data. Passing zero through to `compute_perf_rows` would incorrectly suppress VWAP computation. The existing YF/CG layer already does `vol_usd if vol_usd > 0 else None`, so this is consistent.

## Risks / Trade-offs

- **Limited current coverage** (5 symbols): Most symbols still go via YF/CG. This is intentional; EODHD coverage grows over time without code changes (just by adding to `EODHD_SYMBOL_MAP`). → Mitigation: treat fallback as a feature, not a bug.
- **Pagination**: EODHD returns paged results (default 1000/page). BTC/ETH have ~47k hourly candles = 47 pages. First fetch is slow (~1-2s); subsequent reads come from disk cache. → Mitigation: page through all results in the fetch function, cache aggressively.
- **Timezone offsets**: EODHD timestamps use local exchange timezone (e.g. `+02:00`). Must normalize to UTC before resampling to daily/4H buckets. → Mitigation: always `astimezone(timezone.utc)` in the adapter.
- **Stale cache**: If the EODHD service ingests new candles intra-day, the daily disk cache will be stale until the next calendar day. → Acceptable; same behavior as current YF/CG caches.

## Migration Plan

1. Add `EODHD_SYMBOL_MAP` and `eodhd:` prefix routing to `resolve_source_key()` in `draw_chart.py`
2. Implement `_fetch_from_eodhd()` (with pagination) and `_resample_hourly_to_daily()` in `draw_chart.py`
3. Update `fetch_ohlcv()` to dispatch to EODHD adapter for `eodhd:` keys
4. Update `perf_data.py` to add EODHD hourly cache layer + resample functions; wire into `fetch_5y_candles()` and `fetch_4h_candles()`
5. Update `get_data_source()` to return "EODHD" for EODHD-backed symbols
6. No rollback needed — EODHD paths only activate for symbols explicitly listed in `EODHD_SYMBOL_MAP`; all other symbols are unaffected.

## Open Questions

- Which additional HL symbols should be pre-populated in `EODHD_SYMBOL_MAP` beyond the currently confirmed 5 (BTC, ETH, ADA, ALGO, SKY)? → Populate only symbols confirmed to have data (`total > 0`); add more as they are imported into EODHD.
- Should `SKY` (not currently a major HL symbol) be included in the map? → Yes, include all covered symbols for completeness.
