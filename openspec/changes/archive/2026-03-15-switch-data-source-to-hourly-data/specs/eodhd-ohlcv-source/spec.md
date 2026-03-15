## ADDED Requirements

### Requirement: EODHD adapter fetches hourly candles with pagination

The system SHALL fetch hourly OHLCV candles from the local EODHD service at `http://localhost:8010/v1/ohlcv/{instrument_id}?interval=1h` by iterating through all pages until `next_page` is null, and SHALL cache the full result as `cache/ohlcv/{instrument_id}_eodhd_1h_{YYYY-MM-DD}.json`.

#### Scenario: Full history fetched and cached on first call of the day

- **WHEN** `fetch_ohlcv("eodhd:bitcoin")` is called for the first time today
- **THEN** the adapter iterates all paginated pages until `next_page` is null
- **THEN** the combined candle list (all pages) is written to `cache/ohlcv/bitcoin_eodhd_1h_{today}.json`
- **THEN** the function returns the resampled daily candles

#### Scenario: Cache hit skips API calls

- **WHEN** `fetch_ohlcv("eodhd:bitcoin")` is called again on the same calendar day
- **THEN** no HTTP requests are made to the EODHD service
- **THEN** the cached hourly candles are loaded and resampled to daily in-memory

#### Scenario: Timezone normalization

- **WHEN** EODHD returns timestamps with non-UTC offsets (e.g. `2020-10-24T04:00:00+02:00`)
- **THEN** each timestamp is converted to UTC before being stored in the candle dict
- **THEN** the `date` field in every returned candle has `tzinfo=timezone.utc`

#### Scenario: Zero-volume candles treated as missing volume

- **WHEN** an EODHD candle has `volume: 0.0`
- **THEN** the resulting candle dict has `volume: None`
- **THEN** VWAP computation in `compute_perf_rows` treats this candle as having no volume data

---

### Requirement: EODHD symbol map routes HL symbols to instrument IDs

The system SHALL maintain an `EODHD_SYMBOL_MAP` dict in `draw_chart.py` that maps HL ticker symbols to EODHD `instrument_id` values. `resolve_source_key()` SHALL check this map first and return `eodhd:{instrument_id}` when a match is found.

#### Scenario: BTC resolves to EODHD source

- **WHEN** `resolve_source_key("BTC")` is called
- **THEN** the returned source_key is `"eodhd:bitcoin"`
- **THEN** `get_data_source("BTC")` returns `"EODHD"`

#### Scenario: Symbol not in EODHD falls back to existing routing

- **WHEN** `resolve_source_key("SOL")` is called and SOL is not in `EODHD_SYMBOL_MAP`
- **THEN** the returned source_key follows existing YF/CG routing (e.g. `"SOL-USD"` or `"cg:solana"`)
- **THEN** `get_data_source("SOL")` returns `"Yahoo Finance"` or `"CoinGecko"` as before

#### Scenario: K-scale tokens resolved through EODHD symbol map

- **WHEN** a K-prefix HL symbol (e.g. `KPEPE`) has its underlying token (e.g. `pepe`) in `EODHD_SYMBOL_MAP`
- **THEN** `resolve_source_key("KPEPE")` returns `"eodhd:pepe"` with multiplier `1000.0`

---

### Requirement: EODHD hourly candles are resampled to daily for fetch_ohlcv

The system SHALL resample EODHD hourly candles to 1-day UTC buckets before returning from `fetch_ohlcv()`. Each daily candle SHALL aggregate open (first), high (max), low (min), close (last), and volume (sum of non-None values).

#### Scenario: Hourly candles aggregate to correct daily OHLCV

- **WHEN** EODHD returns 24 hourly candles for a given UTC calendar day
- **THEN** `fetch_ohlcv("eodhd:bitcoin")` returns exactly 1 candle for that day
- **THEN** that daily candle's high equals the maximum of all 24 hourly highs
- **THEN** that daily candle's low equals the minimum of all 24 hourly lows
- **THEN** that daily candle's open equals the first hourly candle's open
- **THEN** that daily candle's close equals the last hourly candle's close

#### Scenario: Partial day produces one daily candle

- **WHEN** today has only N < 24 hourly candles available (intraday)
- **THEN** `fetch_ohlcv("eodhd:bitcoin")` includes a partial candle for today
- **THEN** no error is raised for the incomplete day

---

### Requirement: fetch_5y_candles and fetch_4h_candles use EODHD for covered symbols

The system SHALL route `fetch_5y_candles()` and `fetch_4h_candles()` through the EODHD hourly cache for symbols covered by `EODHD_SYMBOL_MAP`.
