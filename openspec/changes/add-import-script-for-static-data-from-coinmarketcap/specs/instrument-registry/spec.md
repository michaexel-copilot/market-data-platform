## MODIFIED Requirements

### Requirement: Asset-class-specific attribute tables
The system SHALL maintain separate per-asset-class attribute tables (`instrument_crypto`,
`instrument_equity`, `instrument_etf`, `instrument_fx`, `instrument_commodity`) each with a
foreign key `instrument_id` referencing `instruments`. Fields are defined per the proposal's
Static Fields Model.  The `instrument_crypto` table SHALL additionally contain three nullable
CMC-specific columns: `cmc_id INTEGER`, `cmc_slug VARCHAR`, `cmc_rank INTEGER`.

#### Scenario: Crypto instrument attributes stored
- **WHEN** a crypto instrument is ingested
- **THEN** a corresponding row is inserted or updated in `instrument_crypto` with `blockchain_network`, `consensus_mechanism`, `total_supply`, `max_supply`, `circulating_supply`, `decimals`, `whitepaper_url`, `github_url`

#### Scenario: Equity instrument attributes stored
- **WHEN** an equity instrument is ingested
- **THEN** a corresponding row is inserted or updated in `instrument_equity` with `isin`, `cusip`, `figi`, `composite_figi`, `mic_code`, `sic_code`, `country_of_incorporation`, `shares_outstanding`, `float_shares`

#### Scenario: Missing optional fields allowed
- **WHEN** a provider does not supply an optional attribute (e.g. `whitepaper_url`)
- **THEN** the field is stored as `NULL`; the record is still accepted

#### Scenario: CMC columns default to NULL
- **WHEN** a new `instrument_crypto` row is inserted without CMC enrichment
- **THEN** `cmc_id`, `cmc_slug`, and `cmc_rank` are stored as `NULL`

#### Scenario: CMC enrichment populates columns
- **WHEN** the CMC static importer finds a slug match between `cmc_map` and `instruments`
- **THEN** `instrument_crypto.cmc_id`, `cmc_slug`, and `cmc_rank` are updated to the matched values
