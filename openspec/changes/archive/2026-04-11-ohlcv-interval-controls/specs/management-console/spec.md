## MODIFIED Requirements

### Requirement: Fundamentals detail pane
The console SHALL display fundamental data for the selected instrument in the main pane. The data SHALL be fetched from `GET /v1/instruments/{symbol}/fundamentals`. Fields SHALL be rendered as a labelled key-value list. If no instrument is selected, the pane SHALL show a placeholder message. Additionally, after a successful migration (`BTN_MIGRATE_FUNDAMENTALS`), the pane SHALL show "Migration complete — N instruments promoted."

The key-value table SHALL include a **Launch Date** row when the API response contains a non-null `launch_date` field. The value SHALL be displayed as `YYYY-MM-DD`. If `launch_date` is null or absent, the row SHALL be omitted entirely.

Below the fundamentals key-value table, the pane SHALL render two additional sections:

**OHLCV Time Range** — a table populated from `GET /v1/instruments/{id}/ohlcv-availability`.
The table SHALL include the columns **Interval / First / Last / Actions**.
For native intervals (`1m`, `5m`, `1h`, `1d`), the `Actions` cell SHALL contain:
- an **Update** button that calls `POST /v1/instruments/{id}/update-ohlcv/{interval}`;
- an **Auto** checkbox that calls `PUT /v1/instruments/{id}/ohlcv-update-settings/{interval}`.

The Update button SHALL be hidden when that interval's persisted `auto_update` flag is true.
The Update button SHALL be disabled when the interval is not stale yet, using these UTC freshness thresholds:
- `1m` → newer than 1 minute
- `5m` → newer than 5 minutes
- `1h` → newer than 1 hour
- `1d` → same UTC day

The `1m` row SHALL always be present even when no 1m candles have been ingested yet; its `first` and `last` values SHALL display as `—`, and the Update button SHALL remain enabled.
After a successful row-level update or auto-toggle change, the OHLCV sections SHALL be refreshed.

**OHLCV Data Available** — a matrix table with rows per interval (1m/5m/1h/1d) and columns per data source showing ✓ or — per cell, populated from `GET /v1/instruments/{id}/ohlcv-data-available`.

No other sections SHALL be rendered in the fundamentals pane. In particular, a "Best SMA Exit V1" section (`best-sma-v2-section`) SHALL NOT be present.

#### Scenario: `1m` row shown without data
- **WHEN** the selected instrument has no `1m` rows in `ohlcv`
- **THEN** the OHLCV Time Range table still shows a `1m` row with `First = —`, `Last = —`, and an enabled Update button

#### Scenario: Row-level update available for stale interval
- **WHEN** the selected instrument has stale `1h` data and `auto_update = false`
- **THEN** the `1h` row shows an enabled Update button and an unchecked Auto checkbox

#### Scenario: Row-level update hidden when auto is enabled
- **WHEN** the persisted setting for the `5m` interval is `auto_update = true`
- **THEN** the `5m` row hides the Update button and shows the Auto checkbox as checked

#### Scenario: Row-level update refreshes OHLCV sections
- **WHEN** the user clicks the row-level Update button and the backend returns HTTP 200
- **THEN** an inline success message is shown and the OHLCV Time Range and Data Available sections are refreshed

#### Scenario: Row-level update failure shown inline
- **WHEN** the row-level update request returns a non-200 response or throws a network error
- **THEN** the fundamentals pane shows `"<interval> update failed: <error>"`

#### Scenario: Auto toggle persists setting
- **WHEN** the user checks or unchecks the Auto checkbox for a native interval row
- **THEN** the console sends `PUT /v1/instruments/{id}/ohlcv-update-settings/{interval}` with `{ "auto_update": true|false }` and refreshes the OHLCV sections on success
