## 1. Backend support
- [x] Add the `ohlcv_update_settings` migration.
- [x] Always include `1m` in `ohlcv-availability`, even when no records exist.
- [x] Add per-interval OHLCV settings and update endpoints for get/put/post flows.

## 2. Management console UI
- [x] Fetch per-interval settings in the fundamentals view and render an `Actions` column.
- [x] Add per-row `Update` and `Auto` controls with staleness gating and refresh behavior.

## 3. Verification
- [x] Add or update automated tests for the new OHLCV interval controls behavior.
