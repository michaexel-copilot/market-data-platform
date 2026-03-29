# Spec: backtest-cache

## Purpose

Defines how backtest results are persisted to and retrieved from the local cache directory (`cache/backtest/`), including what data is stored and how cached runs are listed.

## Requirements

### Requirement: Cache stores input parameters

Each saved backtest result SHALL include a `_params` key containing all input parameters used to produce it: `ind1_type`, `ind2_type`, `ind1_min`, `ind1_max`, `ind2_min`, `ind2_max`, `exposure`, `train_start`, `train_end`, `val_start`, `symbol`.

#### Scenario: New backtest result persisted with params

WHEN `save_cache()` is called with a result dict and keyword parameters
THEN the saved JSON file SHALL contain a `_params` object with all provided kwargs plus the symbol

#### Scenario: Legacy file without _params key

WHEN `list_cache(symbol)` encounters a cache file that has no `_params` key
THEN it SHALL skip that file silently without raising an error

### Requirement: list_cache returns all results for a symbol

`list_cache(symbol: str) -> list[dict]` SHALL scan `cache/backtest/` for all files matching `{SYMBOL.upper()}_*.json`, load each, and return the parsed dicts (including `_params`, `best_params`, `train_stats`, `val_stats`).

#### Scenario: Multiple cached runs exist

WHEN `list_cache("BTC")` is called and 3 JSON files matching `BTC_*.json` exist
THEN it SHALL return a list of 3 dicts in order of file modification time (newest first)

#### Scenario: No cached runs exist

WHEN `list_cache("XYZ")` is called and no matching files exist
THEN it SHALL return an empty list

### Requirement: Backtest results cached to disk
After a successful optimisation+validation run, the results SHALL be serialised to a JSON file at `cache/backtest/{SYMBOL}_{ind1}_{ind2}_{exposure}_{train_end}_{val_start}.json`. On a subsequent identical POST request, the cached JSON SHALL be read and returned without re-running the backtest.

#### Scenario: Cache file created after first run
- **WHEN** a backtest POST completes successfully
- **THEN** a JSON file SHALL be created at `cache/backtest/` with a filename encoding the key parameters

#### Scenario: Cache hit returns result without re-running
- **WHEN** a backtest POST is made with parameters identical to a previously cached run
- **THEN** the cached JSON SHALL be loaded and no `Backtest.optimize()` call SHALL be made

---

### Requirement: Cache invalidation via DELETE endpoint
The system SHALL expose `DELETE /asset/{symbol}/backtest-cache` which accepts the same parameters as the POST and deletes the matching cache file if it exists.

#### Scenario: DELETE removes matching cache file
- **WHEN** a DELETE request is made to `/asset/BTC/backtest-cache` with matching parameters
- **THEN** the corresponding cache file SHALL be deleted and a 200 OK response returned

#### Scenario: DELETE returns 404 when no cache exists
- **WHEN** a DELETE request is made for a combination that has no cache file
- **THEN** the response SHALL return HTTP 404

---

### Requirement: Clear Cache button in UI
The results section SHALL display a "Clear Cache" button after a backtest has been run. Clicking it SHALL send an HTMX DELETE to `/asset/{symbol}/backtest-cache` with the same parameters, then clear the `#backtest-results` placeholder.

#### Scenario: Clear Cache button visible in results
- **WHEN** a backtest result is displayed
- **THEN** a "Clear Cache" button SHALL be visible in the results section

#### Scenario: Clear Cache empties results placeholder
- **WHEN** the user clicks "Clear Cache" and the DELETE request succeeds
- **THEN** the `#backtest-results` div SHALL be emptied
