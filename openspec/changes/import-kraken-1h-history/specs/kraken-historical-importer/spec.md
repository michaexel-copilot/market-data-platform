## ADDED Requirements

### Requirement: Kraken data source registration
The system SHALL register "Kraken Historical" as a named data source with
`data_source_id = 5` and `short_name = 'kraken_hist'` in the `data_source` table.
The source SHALL have `retrieval_priority = NULL` (import-only, not used for live
ingestion).

#### Scenario: Migration runs on a fresh database
- **WHEN** migration `031_kraken_historical_source.sql` is applied
- **THEN** a row exists in `data_source` with `data_source_id = 5`, `name = 'Kraken Historical'`, `short_name = 'kraken_hist'`, and `retrieval_priority IS NULL`

#### Scenario: Migration is idempotent
- **WHEN** migration `031_kraken_historical_source.sql` is applied a second time
- **THEN** no error occurs and the existing row is unchanged

---

### Requirement: Kraken pair name resolution
The system SHALL resolve a canonical `instrument_id` to a Kraken pair filename prefix
using the following rule:
1. Look up `instrument_id` in `config/kraken_pairs.yaml`; if found, use the mapped value.
2. Otherwise, construct `{ticker.upper()}USD` from `instruments.ticker`.

#### Scenario: Known exception — Bitcoin
- **WHEN** the instrument is `bitcoin` (ticker `BTC`)
- **THEN** the resolved pair is `XBTUSD` (from YAML override)

#### Scenario: Standard asset — Cardano
- **WHEN** the instrument is `cardano` (ticker `ADA`) and no YAML override exists
- **THEN** the resolved pair is `ADAUSD`

#### Scenario: YAML override takes precedence
- **WHEN** an `instrument_id` has an entry in `kraken_pairs.yaml`
- **THEN** the mapped value is used regardless of the ticker value

---

### Requirement: Kraken 1h CSV import CLI
The system SHALL provide a CLI command `import-kraken-1h` that imports 1h OHLCV
rows from a Kraken historical flat file into the `ohlcv` table.

The CSV format is headerless with columns:
`unix_timestamp, open, high, low, close, volume, trade_count`

The command SHALL accept:
- `--symbol SYMBOL` (required): HL/CMC ticker, resolved to `instrument_id`
- `--data-dir PATH` (optional, default `/mnt/ds420/data/kraken/1-hour`): directory containing CSV files

The import SHALL:
- Upsert rows into `ohlcv` with `interval = '1h'`, `source = 'kraken'`,
  `is_aggregated = FALSE`
- Compute `tick_1h = unix_timestamp / 3600`
- Use `ON CONFLICT (instrument_id, interval, ts) DO UPDATE` (idempotent)
- Process rows in batches of 5000
- Update `ohlcv_data_available` setting `has_1h = TRUE` after success

#### Scenario: Successful import for ADA
- **WHEN** `import-kraken-1h --symbol ADA` is run and `ADAUSD_60.csv` exists
- **THEN** all rows are upserted into `ohlcv` for `instrument_id = 'cardano'`, `interval = '1h'`, `source = 'kraken'`
- **THEN** `ohlcv_data_available` has `has_1h = TRUE` for `cardano` / `data_source_id = 5`
- **THEN** the command prints the number of rows upserted

#### Scenario: File not found
- **WHEN** `import-kraken-1h --symbol XYZ` is run and `XYZUSD_60.csv` does not exist
- **THEN** the command exits with a non-zero code and prints the expected file path

#### Scenario: Symbol not found in database
- **WHEN** `import-kraken-1h --symbol UNKNOWNSYM` is run and no instrument matches
- **THEN** the command exits with a non-zero code and prints a clear error

#### Scenario: Re-import is idempotent
- **WHEN** `import-kraken-1h --symbol ADA` is run twice on the same file
- **THEN** the row count in `ohlcv` is unchanged after the second run

---

### Requirement: Gap-status REST endpoint
The system SHALL expose `GET /v1/instruments/{symbol}/kraken-1h-status` returning a
JSON object describing the import status for the given symbol:

```json
{
  "instrument_id": "cardano",
  "kraken_pair": "ADAUSD",
  "has_file": true,
  "launch_date": "2017-09-29",
  "earliest_db_ts": "2023-04-11T00:00:00Z",
  "gap_rows": 47304,
  "already_imported": false
}
```

- `has_file`: whether `{PAIR}_60.csv` exists in the data directory
- `gap_rows`: count of CSV rows with `ts < earliest_db_ts` (0 if none or already imported)
- `already_imported`: `TRUE` if any `ohlcv` row exists with `source = 'kraken'` for this instrument
- `earliest_db_ts`: `MIN(ts)` from `ohlcv` where `interval = '1h'` and `source != 'kraken'`; `NULL` if no non-Kraken 1h data

#### Scenario: File exists with a gap
- **WHEN** `GET /v1/instruments/ada/kraken-1h-status` is called and the file exists and no Kraken rows are in the DB
- **THEN** the response has `has_file: true`, `gap_rows > 0`, `already_imported: false`

#### Scenario: No file available
- **WHEN** `GET /v1/instruments/btc/kraken-1h-status` is called and `XBTUSD_60.csv` does not exist
- **THEN** the response has `has_file: false` and `gap_rows: 0`

#### Scenario: Already imported
- **WHEN** rows with `source = 'kraken'` exist for the instrument
- **THEN** the response has `already_imported: true` and `gap_rows: 0`

#### Scenario: Symbol not found
- **WHEN** the symbol cannot be resolved
- **THEN** the endpoint returns HTTP 404

---

### Requirement: Import-trigger REST endpoint
The system SHALL expose `POST /v1/instruments/{symbol}/import-kraken-1h` that
synchronously runs the import for the given symbol and returns a summary:

```json
{
  "instrument_id": "cardano",
  "rows_inserted": 47304,
  "gap_closed_from": "2017-09-29T00:00:00Z",
  "gap_closed_to": "2023-04-11T00:00:00Z"
}
```

The endpoint SHALL return HTTP 400 if no CSV file exists for the symbol.
The endpoint SHALL return HTTP 404 if the symbol cannot be resolved.
The endpoint SHALL be idempotent (calling twice produces the same DB state).

#### Scenario: Successful trigger
- **WHEN** `POST /v1/instruments/ada/import-kraken-1h` is called and file exists
- **THEN** HTTP 200 is returned with `rows_inserted >= 0` and date range populated

#### Scenario: File missing
- **WHEN** `POST /v1/instruments/xyz/import-kraken-1h` is called and no file exists
- **THEN** HTTP 400 is returned with an error message including the expected file path

#### Scenario: Idempotent second call
- **WHEN** `POST /v1/instruments/ada/import-kraken-1h` is called a second time
- **THEN** HTTP 200 is returned and `rows_inserted` reflects actual upserted (0 if all rows already exist)
