## ADDED Requirements

### Requirement: Yahoo Finance fetch uses fixed start date

The system SHALL fetch daily OHLCV data from Yahoo Finance using `start="2020-01-01"` as the begin date, returning all available candles from that date to today rather than a rolling 1-year window.

#### Scenario: Token with history before 2020
- **WHEN** a Yahoo Finance-backed token (e.g. BTC, ETH, SOL) is fetched
- **THEN** the returned candle list spans from 2020-01-01 (or the token's listing date if later) to the current date
- **THEN** the candle count is greater than 365

#### Scenario: Token launched after 2020
- **WHEN** a Yahoo Finance-backed token that launched after 2020-01-01 (e.g. AVAX launched Jul 2020, DOT launched Aug 2020) is fetched
- **THEN** the returned candle list starts from the token's first available date and continues to today
- **THEN** no error is raised due to the start date predating the token

#### Scenario: Cache stores extended history
- **WHEN** extended history is fetched for the first time today
- **THEN** the full candle list (2020-01-01 to today) is saved to the daily cache file
- **THEN** subsequent calls on the same day return the cached extended list without re-fetching

---

### Requirement: CoinGecko fetch returns true daily candles

The system SHALL fetch daily OHLCV data from CoinGecko using the `/market_chart` endpoint with `?interval=daily&days=2000`, returning one data point per calendar day instead of 4-day aggregates.

#### Scenario: CG-backed token returns daily granularity
- **WHEN** a CoinGecko-backed token (e.g. SUI, HYPE, TAO, MNT) is fetched
- **THEN** consecutive candles in the returned list are separated by approximately 86400 seconds (1 day)
- **THEN** the candle count for a token with 2 years of history is approximately 730 (not ~182 as with 4-day aggregates)

#### Scenario: CG market_chart response mapped to candle format
- **WHEN** a CoinGecko market_chart response is parsed
- **THEN** each `[timestamp_ms, price]` entry is mapped to a candle dict with `date`, `open`, `high`, `low`, `close` all set to the price value (close-only source)
- **THEN** candles are sorted ascending by date

#### Scenario: CG-backed token extended history
- **WHEN** a CoinGecko-backed token that launched in 2023 (e.g. SUI) is fetched with days=2000
- **THEN** the returned candle list starts from the token's first available date (not 2020-01-01)
- **THEN** no error is raised for the period before the token's launch

---

### Requirement: UNI symbol routes to CoinGecko Uniswap data

The system SHALL map the HL symbol `UNI` to the CoinGecko coin ID `uniswap`, bypassing the Yahoo Finance `UNI-USD` ticker which resolves to "UNICORN Token" (an unrelated asset).

#### Scenario: UNI fetches Uniswap price data
- **WHEN** OHLCV data is fetched for HL symbol `UNI`
- **THEN** the returned candle close prices reflect the Uniswap token price (approx. $3–15 range historically, not $0.0002)
- **THEN** the data source reported in the Fundamentals tab reads "CoinGecko"

#### Scenario: UNI chart renders at correct price scale
- **WHEN** a chart is drawn for UNI
- **THEN** the Y-axis range is consistent with Uniswap's historical price (e.g. $2–$45)
- **THEN** the SMA lines are computed on the correct price series
