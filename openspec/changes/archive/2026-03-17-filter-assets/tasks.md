## 1. Database Migration

- [x] 1.1 Create `022_instrument_hyperliquid.sql` migration adding `instrument_hyperliquid` table with composite PK `(instrument_id, network)`, columns `hl_symbol`, `lot_size`, `tick_size`, `max_leverage`, `is_active`, `last_refreshed_at`, and FK to `instruments`
- [x] 1.2 Run migration to verify it applies cleanly (`uv run migrate`)

## 2. Data Model

- [x] 2.1 Add `HLPairRecord` dataclass to `market_data/models/` with fields: `hl_symbol`, `base_ticker`, `lot_size`, `tick_size`, `max_leverage`
- [x] 2.2 Add `HLInstrumentRecord` to the API models (for response serialisation) with the `hyperliquid` sub-object shape

## 3. Hyperliquid Connector

- [x] 3.1 Create `market_data/connectors/hyperliquid.py` implementing the `Connector` protocol with `name = "hyperliquid"`, `supported_asset_classes = [AssetClass.CRYPTO]`, `supported_intervals = []`
- [x] 3.2 Implement `fetch_hl_pairs(network: str) -> list[HLPairRecord]` using `httpx` against `https://api.hyperliquid.xyz/info` (mainnet) and `https://api.hyperliquid-testnet.xyz/info` (testnet) with `{"type": "meta"}` POST body
- [x] 3.3 Implement K-prefix stripping in the connector normalisation step (`KPEPE` → base_ticker `PEPE`, hl_symbol preserved)
- [x] 3.4 Implement `fetch_instruments(asset_class)` that calls `fetch_hl_pairs("mainnet")` and returns `InstrumentRecord` objects for matched instruments
- [x] 3.5 Implement `fetch_ohlcv` raising `NotImplementedError`
- [x] 3.6 Implement `reconcile_hl_pairs(pairs, conn)` function performing case-insensitive ticker lookup and logging unmatched symbols at WARNING level

## 4. DB Persistence Layer

- [x] 4.1 Create `market_data/ingestion/hyperliquid.py` (or extend `db/`) with `upsert_hl_pairs(conn, network, pairs)` — atomically deactivates stale rows then upserts fresh pairs in a single transaction
- [x] 4.2 Implement `get_hl_tradeable_instrument_ids(conn, network) -> set[str]` returning active `instrument_id` values for the given network
- [x] 4.3 Implement `get_hl_metadata_for_instruments(conn, network, instrument_ids) -> dict[str, dict]` returning HL metadata keyed by `instrument_id` (used by the API to embed the `hyperliquid` sub-object)

## 5. Admin REST Endpoint

- [x] 5.1 Add `POST /v1/admin/import-hl-pairs` endpoint in `market_data/api/rest/admin.py` accepting `{"network": "mainnet"|"testnet"}`
- [x] 5.2 Endpoint calls connector `fetch_hl_pairs`, `reconcile_hl_pairs`, `upsert_hl_pairs` and returns `{"upserted": N, "unmatched": M, "deactivated": K}`
- [x] 5.3 Validate `network` field (422 for invalid values)

## 6. Instruments API Filter

- [x] 6.1 Add `tradeable_on: str | None` and `network: str` (default `"mainnet"`) query parameters to `GET /v1/instruments` in `market_data/api/rest/instruments.py`
- [x] 6.2 When `tradeable_on="hyperliquid"`, add `JOIN instrument_hyperliquid USING (instrument_id)` with `is_active = TRUE` and `network = <network>` filter to the query
- [x] 6.3 When `tradeable_on="hyperliquid"`, embed HL metadata as `"hyperliquid": {"hl_symbol": ..., "lot_size": ..., "tick_size": ..., "max_leverage": ...}` in each item
- [x] 6.4 Return HTTP 400 for unknown `tradeable_on` values

## 7. CLI Command

- [x] 7.1 Create `market_data/cli/import_hl_pairs.py` with argument `--network` (default `mainnet`) calling `POST /v1/admin/import-hl-pairs`
- [x] 7.2 Print success summary (`Imported N pairs (M unmatched, K deactivated)`) on stdout; HTTP/connection errors to stderr with exit code 1
- [x] 7.3 Register `import-hl-pairs` entrypoint in `pyproject.toml` under `[project.scripts]`

## 8. Tests

- [x] 8.1 Add unit test for K-prefix stripping in the connector (in `tests/test_connectors.py` or new file)
- [x] 8.2 Add unit test for `reconcile_hl_pairs` with mock DB (matched + unmatched cases)
- [x] 8.3 Add integration test for `POST /v1/admin/import-hl-pairs` with a mock HL API response
- [x] 8.4 Add integration test for `GET /v1/instruments?tradeable_on=hyperliquid` verifying filter and embedded metadata
