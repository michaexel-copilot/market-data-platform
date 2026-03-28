## 1. Enrich launch_date during CMC migrate-fundamentals

- [x] 1.1 In `migrate_fundamentals.py`, add an UPDATE statement that sets `instruments.launch_date = cmc_map.first_historical_data::DATE` for each row where `cmc_map.slug = instruments.instrument_id` and `cmc_map.first_historical_data IS NOT NULL`
- [x] 1.2 Ensure the UPDATE uses `COALESCE` or a conditional so a NULL `first_historical_data` never overwrites an existing non-null `launch_date`

## 2. Expose launch_date in the fundamentals API

- [x] 2.1 In `src/market_data/api/rest/instruments.py`, extend `get_fundamentals()` to also `SELECT launch_date FROM instruments WHERE instrument_id = %s` and include the value (as ISO string or `None`) in the returned dict
- [x] 2.2 Confirm the response field is named `launch_date` and serialises as `"YYYY-MM-DD"` for non-null values

## 3. Render Launch Date in PANE_FUNDAMENTALS

- [x] 3.1 In `src/market_data/api/rest/console.py`, find the JS function that builds the `PANE_FUNDAMENTALS` key-value table rows
- [x] 3.2 Add a conditional row for `launch_date`: if the value is present and non-null, render `<tr><td>Launch Date</td><td><value></td></tr>`; omit the row otherwise

## 4. Tests

- [x] 4.1 Add or extend a unit/integration test in `tests/` to assert that `GET /v1/instruments/{symbol}/fundamentals` returns a `launch_date` field for an instrument that has one populated
- [x] 4.2 Add a test that asserts `launch_date` is absent (or null) in the response when the field is null in the database
- [x] 4.3 Add a test for `migrate_fundamentals` (or the existing test fixture) that confirms `instruments.launch_date` is populated after enrichment when `cmc_map.first_historical_data` is set
