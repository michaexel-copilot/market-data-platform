## ADDED Requirements

### Requirement: instrument_hyperliquid table schema
The system SHALL maintain an `instrument_hyperliquid` table with composite primary key `(instrument_id, network)`. Columns SHALL be: `instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id)`, `network TEXT NOT NULL CHECK (network IN ('mainnet', 'testnet'))`, `hl_symbol TEXT NOT NULL` (e.g. `BTC/USDC:USDC`), `lot_size DOUBLE PRECISION NOT NULL`, `tick_size DOUBLE PRECISION NOT NULL`, `max_leverage DOUBLE PRECISION NOT NULL`, `is_active BOOLEAN NOT NULL DEFAULT TRUE`, `last_refreshed_at TIMESTAMPTZ NOT NULL`.

#### Scenario: Row inserted for matched pair
- **WHEN** a pair is successfully reconciled and upserted
- **THEN** a row exists in `instrument_hyperliquid` with `instrument_id`, `network`, `hl_symbol`, `lot_size`, `tick_size`, `max_leverage`, `is_active = TRUE`, and `last_refreshed_at` set to the current UTC timestamp

#### Scenario: Existing row updated on re-import
- **WHEN** `import-hl-pairs` is run again for the same network
- **THEN** existing rows are updated in place (upsert by `(instrument_id, network)`) rather than duplicated

#### Scenario: Stale pairs marked inactive
- **WHEN** an import run completes and a previously active pair is no longer returned by the HL API
- **THEN** its `is_active` is set to `FALSE` and `last_refreshed_at` is updated

---

### Requirement: DB upsert helper
The system SHALL provide a `upsert_hl_pairs(conn, network, pairs)` function that accepts a DB connection, a network string, and a list of `(instrument_id, HLPairRecord)` tuples. It SHALL atomically set `is_active = FALSE` for all existing rows for that network, then upsert each pair with `is_active = TRUE`.

#### Scenario: Atomic replacement of network pairs
- **WHEN** `upsert_hl_pairs` is called with a list of 100 mainnet pairs
- **THEN** any previously active mainnet rows not in the new list are marked `is_active = FALSE`, and all 100 provided pairs are upserted with `is_active = TRUE`, in a single transaction

#### Scenario: Empty input deactivates all
- **WHEN** `upsert_hl_pairs` is called with an empty list (HL API returned zero pairs)
- **THEN** all existing rows for that network are set to `is_active = FALSE`; no rows are inserted

---

### Requirement: DB query helper — filter by tradeable_on
The system SHALL provide a `get_hl_tradeable_instrument_ids(conn, network) -> set[str]` function that returns the set of `instrument_id` values with `is_active = TRUE` in `instrument_hyperliquid` for the given network.

#### Scenario: Returns active instrument IDs for network
- **WHEN** `get_hl_tradeable_instrument_ids(conn, "mainnet")` is called
- **THEN** a set of `instrument_id` strings is returned containing only those with `is_active = TRUE` and `network = 'mainnet'`

#### Scenario: Returns empty set when no data
- **WHEN** no rows exist in `instrument_hyperliquid` for the requested network
- **THEN** an empty set is returned
