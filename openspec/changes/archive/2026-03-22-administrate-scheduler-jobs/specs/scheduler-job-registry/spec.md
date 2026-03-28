# Scheduler Job Registry

## Purpose

Defines the persistent storage layer for scheduler job enabled/disabled state. The `scheduler_jobs` table is the source of truth for which APScheduler jobs are active at startup and across restarts.

## Requirements

### Requirement: Scheduler jobs table
The system SHALL maintain a `scheduler_jobs` table in PostgreSQL with columns `job_id TEXT PRIMARY KEY`, `enabled BOOL NOT NULL DEFAULT true`, and `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`.

#### Scenario: Table created by migration
- **WHEN** the migration `029_scheduler_jobs.sql` is applied
- **THEN** the `scheduler_jobs` table exists with the correct schema

#### Scenario: Seeded with known jobs
- **WHEN** the migration is applied for the first time
- **THEN** the table contains exactly four rows: `ohlcv_1m`, `ohlcv_5m`, `ohlcv_1h`, `ohlcv_1d`, all with `enabled = true`

---

### Requirement: Load job states at startup
The system SHALL expose a `load_job_states(db) -> dict[str, bool]` function that reads all rows from `scheduler_jobs` and returns a mapping of `job_id` to `enabled`. A job ID absent from the table SHALL default to `True`.

#### Scenario: All jobs enabled
- **WHEN** all four rows in `scheduler_jobs` have `enabled = true`
- **THEN** `load_job_states()` returns `{"ohlcv_1m": True, "ohlcv_5m": True, "ohlcv_1h": True, "ohlcv_1d": True}`

#### Scenario: One job disabled
- **WHEN** `ohlcv_1m` has `enabled = false` in the table
- **THEN** `load_job_states()` returns `{"ohlcv_1m": False, ...}` for that entry

#### Scenario: Unknown job ID defaults to enabled
- **WHEN** a `job_id` is passed to logic that calls `load_job_states()` but is not present in the table
- **THEN** the default value `True` is used for that job

---

### Requirement: Set job enabled state
The system SHALL expose a `set_job_enabled(db, job_id: str, enabled: bool) -> None` function that updates the `enabled` column and sets `updated_at = now()` for the given `job_id`. If `job_id` does not exist in the table the function SHALL raise `ValueError`.

#### Scenario: Disable an existing job
- **WHEN** `set_job_enabled(db, "ohlcv_1m", False)` is called
- **THEN** the `ohlcv_1m` row has `enabled = false` and `updated_at` is refreshed

#### Scenario: Re-enable a disabled job
- **WHEN** `set_job_enabled(db, "ohlcv_1m", True)` is called after it was disabled
- **THEN** the `ohlcv_1m` row has `enabled = true`

#### Scenario: Unknown job ID raises ValueError
- **WHEN** `set_job_enabled(db, "nonexistent_job", False)` is called
- **THEN** a `ValueError` is raised

---

### Requirement: Scheduler honours enabled state at startup
`build_scheduler(enabled_jobs: set[str] | None = None)` SHALL only register jobs whose ID appears in `enabled_jobs`. When `enabled_jobs` is `None`, all jobs SHALL be registered (backward-compatible default).

#### Scenario: All jobs enabled at startup
- **WHEN** `build_scheduler()` is called with `enabled_jobs=None`
- **THEN** all four APScheduler jobs are registered

#### Scenario: One job disabled at startup
- **WHEN** `build_scheduler(enabled_jobs={"ohlcv_5m", "ohlcv_1h", "ohlcv_1d"})` is called
- **THEN** only three jobs are registered; `ohlcv_1m` is absent from the scheduler

#### Scenario: Entry points load DB state before building scheduler
- **WHEN** either `uv run serve` or `uv run scheduler` starts
- **THEN** `load_job_states()` is called before `build_scheduler()` and the result is passed as `enabled_jobs`
