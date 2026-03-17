## Why

The market-data-platform holds a broad instrument registry (sourced from CoinMarketCap, EODHD, etc.) but has no record of which instruments are actually tradeable as perpetual futures on Hyperliquid. Without this intersection, consumers like FindShortOpportunities cannot query the platform for "only the instruments I can trade on HL" — they must maintain a separate CSV file outside the platform.

## What Changes

- Add a new `instrument_hyperliquid` table that stores per-instrument Hyperliquid perpetual metadata (HL symbol, lot size, tick size, max leverage, network: mainnet/testnet).
- Add a Hyperliquid connector that fetches the live perpetual pairs list from the Hyperliquid public API and reconciles it with the instrument registry (matching by ticker).
- Extend `GET /v1/instruments` with a `tradeable_on=hyperliquid` filter parameter that returns only instruments present in `instrument_hyperliquid`.
- Add a CLI command `market-data import-hl-pairs [--testnet|--mainnet]` for on-demand refresh of the Hyperliquid pairs data.

## Capabilities

### New Capabilities

- `hyperliquid-connector`: Fetches the live Hyperliquid perpetual pairs list (mainnet + testnet) via the public Hyperliquid API. Maps pair symbols to canonical instrument tickers, normalises lot size / tick size / max leverage, and upserts into `instrument_hyperliquid`. Handles the Hyperliquid K-prefix convention (e.g. `KPEPE` → `PEPE`).
- `hyperliquid-pairs-store`: Defines the `instrument_hyperliquid` schema: one row per (instrument_id, network) pair with columns `hl_symbol`, `lot_size`, `tick_size`, `max_leverage`, `is_active`, `last_refreshed_at`. Provides DB-layer upsert and query helpers.

### Modified Capabilities

- `unified-market-data-api`: Add optional query parameter `tradeable_on` (values: `hyperliquid`) to `GET /v1/instruments`. When set, only instruments with a matching active row in `instrument_hyperliquid` (for the requested network, defaulting to mainnet) are returned, including their HL metadata in each instrument record.

## Impact

- **New DB migration**: adds `instrument_hyperliquid` table.
- **New connector module**: `market_data/connectors/hyperliquid.py` implementing the `Connector` protocol (`fetch_instruments` only; `fetch_ohlcv` raises `NotImplementedError`).
- **New CLI entrypoint**: `import-hl-pairs` in `market_data/cli/`.
- **API change (additive)**: new `tradeable_on` query param on `GET /v1/instruments` — backwards compatible.
- **FindShortOpportunities**: can replace the local `hl_mainnet_pairs.csv` / `hl_testnet_pairs.csv` files with API calls to the market-data-platform.
- **No breaking changes** to existing endpoints or tables.
