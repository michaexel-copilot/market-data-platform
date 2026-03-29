## Context

The backtest results panel (`backtest_results.html`) and the history table (`backtest_history.html`) are functional but have three usability gaps: the validation trades table renders in full every time regardless of size, there is no way to remove a single history entry without re-running everything with different params, and the "Clear Cache" button wipes all results for a symbol in one click with no granularity.

## Goals / Non-Goals

**Goals:**
- Wrap the validation trades table in a Bootstrap collapse so it defaults to hidden and can be toggled
- Add a per-row Delete button in the history table that removes only that entry's cache file
- Remove the "Clear Cache" button entirely from the results panel

**Non-Goals:**
- Bulk-deleting multiple history entries at once
- Confirmation dialogs for single-row delete (immediate delete is acceptable)
- Any sorting or filtering of the history table

## Decisions

### D1: Val trades collapse targets an existing div by ID

The validation trades section inside `backtest_results.html` already has a surrounding `<div>`. Wrap the table in a Bootstrap collapse div and add a toggle button above it. Use `collapse show` so the toggle button label reads "Hide trades" by default if preferred, but default to collapsed (`collapse` without `show`) to reduce clutter.

**Alternative considered**: Separate HTMX endpoint to load trades on demand. Rejected — trades are already in the rendered HTML so a simple CSS collapse is sufficient and has no round-trip cost.

### D2: Delete button sends `DELETE /asset/{symbol}/backtest-cache/file/{filename}`

The history table rows are rendered server-side and the cache file name is derivable from the `_params` stored inside each result. Pass the sanitized filename as a path segment. The endpoint calls a new `delete_cache_file(filename)` function in `backtest_engine.py` that resolves the filename against `BACKTEST_CACHE_DIR` (no path traversal possible via `Path(...).name`).

On success, the endpoint returns an empty 200 response. The Delete button uses `hx-delete` + `hx-target="closest tr"` + `hx-swap="outerHTML"` to remove the row without reloading the full table.

**Alternative considered**: Pass full `_params` query args like the existing delete endpoint. Rejected — file name is simpler and already available in the rendered row.

### D3: Remove "Clear Cache" button — no replacement

The Clear Cache button and its `DELETE /asset/{symbol}/backtest-cache` endpoint are removed from the template. The endpoint itself can stay in `web.py` for now (not a breaking change to keep it unused).

## Risks / Trade-offs

- **Filename as path segment**: Sanitized by taking `Path(filename).name` server-side, preventing traversal. Only files in `BACKTEST_CACHE_DIR` can be deleted.
- **Row removal without refresh**: After `hx-swap="outerHTML"` removes the `<tr>`, the table is consistent. If the delete fails (404/500), HTMX won't swap and the row stays — acceptable behavior.
