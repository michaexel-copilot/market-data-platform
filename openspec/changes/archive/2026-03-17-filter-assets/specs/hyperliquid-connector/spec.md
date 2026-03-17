## ADDED Requirements

### Requirement: Hyperliquid connector — fetch perpetual pairs
The system SHALL provide a `HyperliquidConnector` class in `market_data/connectors/hyperliquid.py` that implements the `Connector` protocol. It SHALL implement `fetch_instruments(asset_class)` to fetch the live list of perpetual pairs from the Hyperliquid public REST API. It SHALL expose a `fetch_hl_pairs(network: str) -> list[HLPairRecord]` method returning raw HL trading metadata. `fetch_ohlcv` SHALL raise `NotImplementedError`. The connector SHALL declare `name = "hyperliquid"`, `supported_asset_classes = [AssetClass.CRYPTO]`, and `supported_intervals = []`.

#### Scenario: Connector fetches mainnet pairs
- **WHEN** `fetch_hl_pairs(network="mainnet")` is called
- **THEN** a list of `HLPairRecord` objects is returned, each containing `hl_symbol`, `base_ticker`, `lot_size`, `tick_size`, and `max_leverage` sourced from the Hyperliquid mainnet `/info` endpoint

#### Scenario: Connector fetches testnet pairs
- **WHEN** `fetch_hl_pairs(network="testnet")` is called
- **THEN** a list of `HLPairRecord` objects is returned from the Hyperliquid testnet `/info` endpoint

#### Scenario: K-prefix stripped during normalisation
- **WHEN** a Hyperliquid pair has a symbol like `KPEPE` (kilo-unit convention)
- **THEN** the returned `HLPairRecord.base_ticker` is `PEPE` (K-prefix stripped, original `hl_symbol` preserved as-is)

#### Scenario: fetch_ohlcv raises NotImplementedError
- **WHEN** `fetch_ohlcv` is called on the Hyperliquid connector
- **THEN** `NotImplementedError` is raised

#### Scenario: API unavailable
- **WHEN** the Hyperliquid API is unreachable or returns a non-2xx status
- **THEN** `httpx.HTTPError` propagates to the caller; no partial data is returned

---

### Requirement: Hyperliquid connector — instrument reconciliation
The system SHALL provide a `reconcile_hl_pairs(pairs, conn)` function that matches each `HLPairRecord` to an existing instrument in the canonical registry by `base_ticker` (case-insensitive lookup against `instruments.ticker`). Matched pairs are returned as `(instrument_id, HLPairRecord)` tuples. Unmatched pairs SHALL be logged at `WARNING` level and excluded from results.

#### Scenario: Matched pair returned
- **WHEN** a `HLPairRecord` with `base_ticker = "BTC"` is reconciled and a row exists in `instruments` with `ticker = "BTC"`
- **THEN** the returned tuple contains the matching `instrument_id` and the original `HLPairRecord`

#### Scenario: Unmatched pair logged and skipped
- **WHEN** a `HLPairRecord` has a `base_ticker` with no match in `instruments`
- **THEN** it is excluded from results and a `WARNING` log entry records the unmatched symbol

#### Scenario: Case-insensitive match
- **WHEN** `instruments.ticker` is `"ada"` and `HLPairRecord.base_ticker` is `"ADA"`
- **THEN** the pair is matched successfully
