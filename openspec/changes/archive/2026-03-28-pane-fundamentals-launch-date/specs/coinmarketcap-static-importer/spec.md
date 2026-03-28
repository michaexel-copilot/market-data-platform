## MODIFIED Requirements

### Requirement: Enrich instrument_crypto with CMC metadata
After ingesting listing snapshots, the importer SHALL update `instrument_crypto` rows where
the `slug` from `cmc_map` matches `instrument_id` in `instruments`, setting `cmc_id`,
`cmc_slug`, and `cmc_rank` (latest rank from `cmc_map`).

Additionally, the migration SHALL update `instruments.launch_date` with
`cmc_listing_snapshots.date_added::DATE` for each matched instrument, but only when
`date_added IS NOT NULL`. An existing non-null `launch_date` SHALL be overwritten only if
`date_added` is also non-null (i.e. the CMC value is always preferred as the authoritative
source).

#### Scenario: Slug match enriches instrument
- **WHEN** `cmc_map.slug` equals an existing `instruments.instrument_id`
- **THEN** the corresponding `instrument_crypto` row is updated with `cmc_id`, `cmc_slug`, and `cmc_rank`

#### Scenario: Slug match sets launch_date
- **WHEN** a `cmc_listing_snapshots` row matches an existing `instruments` row by ticker and `date_added IS NOT NULL`
- **THEN** `instruments.launch_date` is set to `date_added::DATE`

#### Scenario: Null date_added skips launch_date
- **WHEN** a matched listing snapshot row has `date_added IS NULL`
- **THEN** `instruments.launch_date` is left unchanged

#### Scenario: No matching instrument
- **WHEN** a CMC slug has no corresponding `instruments` row
- **THEN** no row is created; the importer logs DEBUG "No instrument match for slug <slug>"
