## ADDED Requirements

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
