## ADDED Requirements

### Requirement: POST /v1/admin/import-cmc-static endpoint
The system SHALL provide a REST endpoint `POST /v1/admin/import-cmc-static` that
triggers the CoinMarketCap static TSV import on the server side. The accepted body
fields are:
- `dir` (string, optional): filesystem path to the snapshot directory. If omitted,
  the server uses the `CMC_STATIC_DIR` environment variable.

The endpoint SHALL return HTTP 200 with the import counts dict returned by `run_import()`
when successful. If neither `dir` nor `CMC_STATIC_DIR` resolves to an existing
directory, the endpoint SHALL return HTTP 422.

#### Scenario: Successful import using environment variable
- **WHEN** `POST /v1/admin/import-cmc-static` is called with an empty body and `CMC_STATIC_DIR` is set to a valid directory on the server
- **THEN** the response is HTTP 200 with a JSON object containing import counts (e.g. `{"listing": 150, "map": 150, ...}`)

#### Scenario: Successful import with explicit dir
- **WHEN** `POST /v1/admin/import-cmc-static` is called with body `{"dir": "/data/cmc"}`
- **THEN** the directory `/data/cmc` is scanned and the response is HTTP 200 with import counts

#### Scenario: No directory configured
- **WHEN** `POST /v1/admin/import-cmc-static` is called with no body and `CMC_STATIC_DIR` is not set
- **THEN** the response is HTTP 422 with `{"error": "No directory specified and CMC_STATIC_DIR is not set"}`

#### Scenario: Directory does not exist
- **WHEN** `POST /v1/admin/import-cmc-static` is called with a `dir` that does not exist on the server filesystem
- **THEN** the response is HTTP 422 with `{"error": "Directory does not exist: <path>"}`
