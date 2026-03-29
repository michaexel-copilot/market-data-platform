## 1. Backend

- [x] 1.1 Add `delete_cache_file(filename: str) -> bool` to `backtest_engine.py` — resolves `Path(filename).name` against `BACKTEST_CACHE_DIR`, deletes if exists, returns `True`/`False`
- [x] 1.2 Add `DELETE /asset/{symbol}/backtest-cache/file/{filename}` endpoint to `web.py` — calls `delete_cache_file`, returns 200 on success and 404 if not found
- [x] 1.3 Expose the cache filename on each history result — in `list_cache()` or `backtest_history` endpoint, add a `_filename` key (stem of the file) to each result dict so the template can pass it to the delete endpoint

## 2. History table delete button

- [x] 2.1 Add a "Delete" column to `templates/backtest_history.html` with a button per row that uses `hx-delete="/asset/{{ symbol }}/backtest-cache/file/{{ r._filename }}"`, `hx-target="closest tr"`, and `hx-swap="outerHTML"`

## 3. Collapsible validation trades

- [x] 3.1 In `templates/backtest_results.html`, wrap the validation trades table in a `<div id="val-trades-collapse" class="collapse">` and add a toggle button above it (`data-bs-toggle="collapse" data-bs-target="#val-trades-collapse"`)

## 4. Remove Clear Cache button

- [x] 4.1 Remove the "Clear Cache" button block from `templates/backtest_results.html`
