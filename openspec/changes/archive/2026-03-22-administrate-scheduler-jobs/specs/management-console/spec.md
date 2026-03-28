## ADDED Requirements

### Requirement: Scheduler nav button
The console SHALL display a `BTN_NAV_SCHEDULER` button (labelled "⚙ Scheduler") in the top bar alongside the asset-class segment buttons. Clicking it SHALL hide the instrument list pane and the content pane and show the `#PANE_SCHEDULER` div. Clicking any asset-class button while `#PANE_SCHEDULER` is visible SHALL hide `#PANE_SCHEDULER` and restore the normal two-pane layout.

#### Scenario: Navigate to scheduler panel
- **WHEN** the user clicks `BTN_NAV_SCHEDULER`
- **THEN** the instrument list pane and content pane are hidden; `#PANE_SCHEDULER` is visible and populated with the jobs table

#### Scenario: Return to instruments view
- **WHEN** `#PANE_SCHEDULER` is visible and the user clicks an asset-class button
- **THEN** `#PANE_SCHEDULER` is hidden; the instrument list pane and content pane are restored

---

### Requirement: Scheduler jobs table in console
The `#PANE_SCHEDULER` panel SHALL display a table with one row per scheduler job. Each row SHALL show: `job_id`, trigger description, `enabled` status, `next_run_time` (formatted as `YYYY-MM-DD HH:MM UTC` or `—` if null), and an action button labelled "Disable" when the job is enabled or "Enable" when it is disabled.

#### Scenario: Jobs table rendered
- **WHEN** the user navigates to `#PANE_SCHEDULER`
- **THEN** the table shows four rows, one for each known job, with correct `enabled` status and `next_run_time`

#### Scenario: Disabled job row
- **WHEN** a job has `enabled: false`
- **THEN** its row shows `enabled: false`, `next_run_time: —`, and an "Enable" action button

---

### Requirement: Toggle job from console
Clicking the action button in a job row SHALL call the corresponding REST endpoint (`/enable` or `/disable`). During the request the button SHALL be disabled and its label changed to "…". On success the jobs table SHALL be reloaded and re-rendered. On failure an inline error message SHALL appear inside `#PANE_SCHEDULER`.

#### Scenario: Disable a job from the console
- **WHEN** the user clicks "Disable" on an enabled job row
- **THEN** the button is disabled with label "…" during the request; on success the row updates to show `enabled: false` and an "Enable" button

#### Scenario: Enable a job from the console
- **WHEN** the user clicks "Enable" on a disabled job row
- **THEN** on success the row updates to show `enabled: true` and a "Disable" button; `next_run_time` becomes non-null

#### Scenario: Toggle fails
- **WHEN** the toggle REST call returns a non-2xx response
- **THEN** an inline error message is shown in `#PANE_SCHEDULER`; the action button is restored to its original label
