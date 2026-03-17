## Context

The market-data-platform manages a broad canonical instrument registry sourced from CoinMarketCap, EODHD, and others. ShortDesk (the trading UI) targets Hyperliquid perpetual futures exclusively, but currently maintains its own local CSV files (`hl_testnet_pairs.csv`, `hl_mainnet_pairs.csv`) to track which instruments are available on HL and their trading parameters (lot size, tick size, max leverage). These CSV files are maintained manually and go stale.

The platform already has a well-established connector pattern (`market_data/connectors/`), a migration-based DB schema, and a REST API that exposes `GET /v1/instruments`. The goal is to extend all three layers consistently.

The Hyperliquid public REST API (`https://api.hyperliquid.xyz/info`) is key-less; it returns the full list of perpetual instruments (mainnet) with trading metadata via a `POST` with `{"type": "meta"}`. A separate testnet endpoint exists at `https://api.hyperliquid-testnet.xyz/info`.

## Goals / Non-Goals

**Goals:**
- Store HL perpetual metadata per instrument in the DB (HL symbol, lot size, tick size, max leverage, network, is_active).
- Provide a connector that fetches and reconciles HL pairs against the canonical registry.
- Expose `GET /v1/instruments?tradeable_on=hyperliquid` for consumers to query the intersection.
- Provide a CLI command to trigger a refresh on demand.

**Non-Goals:**
- OHLCV data from Hyperliquid (Hyperliquid does not offer open historical OHLCV; this remains out of scope).
- Account-level or order management (that lives in ShortDesk / hl_client).
- Auto-scheduling of HL pair refreshes (manual CLI refresh is sufficient for now).
- Creating new instruments from HL that have no match in the canonical registry.

## Decisions

### Decision 1: New `instrument_hyperliquid` table with composite PK `(instrument_id, network)`

HL has separate mainnet and testnet pair lists that may differ. A composite PK `(instrument_id, network)` (where `network` is `mainnet` or `testnet`) captures both cleanly without requiring a separate table per network.

Columns: `instrument_id TEXT FK → instruments`, `network TEXT CHECK ('mainnet','testnet')`, `hl_symbol TEXT` (e.g. `BTC/USDC:USDC`), `lot_size DOUBLE PRECISION`, `tick_size DOUBLE PRECISION`, `max_leverage DOUBLE PRECISION`, `is_active BOOLEAN DEFAULT TRUE`, `last_refreshed_at TIMESTAMPTZ`.

**Alternative considered**: store mainnet/testnet as two columns in a single row per instrument. Rejected — more complex queries and harder to add future networks.

### Decision 2: Hyperliquid connector implements `fetch_instruments` only

Following the existing Connector protocol, the HL connector will implement `fetch_instruments(asset_class)` returning `InstrumentRecord` objects. `fetch_ohlcv` will raise `NotImplementedError` consistent with the OpenFIGI connector pattern.

The connector also exposes a non-protocol method `fetch_hl_pairs(network)` returning a list of `HLPairRecord` dataclass objects with HL-specific fields (hl_symbol, lot_size, tick_size, max_leverage).

**Alternative considered**: a standalone ingestion module outside the connector framework. Rejected — reusing the connector protocol keeps the architecture consistent.

### Decision 3: Symbol matching by ticker, with K-prefix stripping

Hyperliquid uses a `K`-prefix convention for kilo-unit tokens (e.g. `KPEPE` represents 1000 PEPE). During reconciliation, the connector strips this prefix and looks up the canonical `ticker` in `instruments`. Unmatched symbols are logged as warnings but do not block the import.

**Alternative considered**: store a `hl_ticker` in `instrument_identifiers` with `id_type='hl_symbol'`. Rejected — the existing `ticker_source_map` table already handles cross-source ticker mapping and would add complexity; `instrument_hyperliquid` is self-contained.

### Decision 4: CLI triggers a REST admin endpoint (same pattern as `import-ohlcv`)

The `import-hl-pairs` CLI calls `POST /v1/admin/import-hl-pairs` with `{"network": "mainnet"|"testnet"}`. The admin endpoint runs the connector, reconciles, and upserts. This separates network I/O and DB logic from CLI argument parsing, consistent with how `import-ohlcv` works.

### Decision 5: `tradeable_on=hyperliquid` filter on `GET /v1/instruments`

The filter adds a `JOIN instrument_hyperliquid USING (instrument_id)` when `tradeable_on=hyperliquid` is present. An optional `network` parameter (default: `mainnet`) selects which network's pairs to include. The HL metadata (hl_symbol, lot_size, tick_size, max_leverage) is included in each instrument item's response when the filter is active.

## Risks / Trade-offs

- **HL API instability** → The public HL API has no SLA. If the endpoint changes, the import silently returns 0 pairs. Mitigation: the admin endpoint returns the count of upserted rows; the CLI prints a warning if count is 0.
- **Symbol drift** → HL may list instruments not yet in the canonical registry. Mitigation: unmatched pairs are logged but skipped; a future feature can auto-create instruments from HL.
- **Testnet/mainnet divergence** → Testnet pairs change frequently. Mitigation: import is always triggered manually; consumers specify `network=testnet` explicitly.
- **`is_active` staleness** → Delisted HL instruments remain with `is_active=TRUE` until the next import. Mitigation: each import run sets `is_active=FALSE` for any pair no longer returned by the API before upserting fresh data.

## Migration Plan

1. Add migration `022_instrument_hyperliquid.sql` creating the new table.
2. Deploy API with new `tradeable_on` query parameter (additive, backwards compatible).
3. Register `import-hl-pairs` CLI entrypoint in `pyproject.toml`.
4. Run `market-data import-hl-pairs --mainnet` and `--testnet` once to seed data.
5. ShortDesk can then replace its CSV lookups with `GET /v1/instruments?tradeable_on=hyperliquid&network=mainnet`.

**Rollback**: drop migration `022_instrument_hyperliquid.sql`; remove the `tradeable_on` filter; remove CLI entrypoint. No existing data is modified.

## Open Questions

- Should `hl_symbol` (e.g. `BTC/USDC:USDC`) be stored verbatim or normalised to just the base ticker? Current decision: store verbatim for full fidelity; consumers can derive the base.
- Should the admin import endpoint be protected by an auth token? Currently consistent with other admin endpoints (no auth). Deferred.
