## ADDED Requirements

### Requirement: Cached results endpoint by filename

The system SHALL expose `GET /asset/{symbol}/backtest-cache/file/{filename}/results` that loads the specified cache file from `cache/backtest/` and returns a rendered `backtest_results.html` HTML partial.

#### Scenario: File exists and is valid

- **WHEN** `GET /asset/BTC/backtest-cache/file/BTC_sma_sma_long_cash_abc123.json/results` is called and the file exists with valid content
- **THEN** it SHALL return the rendered backtest results HTML (Best Parameters Found card, train/val stats, validation trades table)

#### Scenario: File not found

- **WHEN** the specified filename does not exist in `cache/backtest/`
- **THEN** it SHALL return an HTML error partial with a human-readable message (not a 500)

### Requirement: list_cache includes filename in each result

`list_cache(symbol)` SHALL inject a `_filename` key into each returned dict containing the bare filename (e.g. `BTC_sma_sma_long_cash_abc123.json`) so that callers can reference the specific cache file.

#### Scenario: list_cache returns _filename

- **WHEN** `list_cache("BTC")` is called and cache files exist
- **THEN** each returned dict SHALL contain a `_filename` key equal to the filename (not the full path) of the source file
