## ADDED Requirements

### Requirement: History table has per-row delete

Each row in the backtest history table SHALL have a "Delete" button that, when clicked, removes only that cached result without affecting other entries.

#### Scenario: Delete button removes the row

WHEN the user clicks the Delete button on a history row
THEN a `DELETE` request SHALL be sent to `/asset/{symbol}/backtest-cache/file/{filename}`
AND the row SHALL be removed from the table on success

#### Scenario: Only the targeted entry is deleted

WHEN a delete request succeeds
THEN all other history rows SHALL remain unchanged

### Requirement: History delete endpoint

`DELETE /asset/{symbol}/backtest-cache/file/{filename}` SHALL delete the specified cache file for the given symbol.

#### Scenario: Valid filename deletes file

WHEN a valid cache filename is provided
THEN the corresponding file in `cache/backtest/` SHALL be deleted and HTTP 200 returned

#### Scenario: Invalid or missing filename returns 404

WHEN a filename that does not exist is provided
THEN the endpoint SHALL return HTTP 404

#### Scenario: Path traversal is blocked

WHEN the filename contains path separators or `..`
THEN only the basename is used to resolve the file, preventing traversal outside `cache/backtest/`

## MODIFIED Requirements

### Requirement: Clear Cache button removed

The "Clear Cache" button SHALL be removed from the backtest results panel (`backtest_results.html`).

#### Scenario: Clear Cache button is absent

WHEN backtest results are displayed
THEN no "Clear Cache" button SHALL be present in the UI
