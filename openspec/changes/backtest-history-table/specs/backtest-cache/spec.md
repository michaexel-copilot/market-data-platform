## ADDED Requirements

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
