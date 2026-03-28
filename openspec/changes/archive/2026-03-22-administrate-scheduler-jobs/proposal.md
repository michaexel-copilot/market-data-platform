## Why

There is currently no way to enable or disable individual scheduler jobs without editing code and restarting the service. This makes operational control impossible at runtime and forces all four ingestion intervals to always run together, which is a problem when a connector is noisy, rate-limited, or simply not needed.

## What Changes

- A new `scheduler_jobs` PostgreSQL table stores the enabled/disabled state of every known job; it is seeded on migration with all four current jobs (`ohlcv_1m`, `ohlcv_5m`, `ohlcv_1h`, `ohlcv_1d`) enabled
- `build_scheduler()` reads the table at startup and only registers jobs whose `enabled` flag is `true`
- A module-level scheduler reference is exposed so REST endpoints can reach the live APScheduler instance
- Three new REST endpoints allow operators to list jobs and toggle them at runtime; changes are persisted to the DB and applied live via APScheduler `pause_job`/`resume_job`
- A new "Scheduler" section is added to the management console HTML UI, accessible from the top bar, showing a table of all jobs with toggle buttons

## Capabilities

### New Capabilities

- `scheduler-job-registry`: DB table `scheduler_jobs`, migration file, and Python helper (`load_job_states`, `set_job_enabled`) for reading and updating job-enabled state
- `scheduler-job-admin-api`: REST endpoints `GET /v1/admin/scheduler/jobs`, `POST /v1/admin/scheduler/jobs/{job_id}/enable`, and `POST /v1/admin/scheduler/jobs/{job_id}/disable`

### Modified Capabilities

- `management-console`: A new top-bar nav button ("⚙ Scheduler") and full-width `#PANE_SCHEDULER` panel are added; the panel fetches and renders the jobs table with per-row enable/disable toggle buttons

## Impact

- **New files**: `src/market_data/db/migrations_pg/029_scheduler_jobs.sql`, `src/market_data/db/scheduler_jobs.py`
- **Modified files**: `src/market_data/ingestion/scheduler.py`, `src/market_data/api/rest/admin.py`, `src/market_data/api/__init__.py`, `src/market_data/api/rest/console.py`
- **No breaking changes**: `build_scheduler()` signature gains an optional parameter; callers that pass nothing get the current all-jobs behaviour
- **Database**: one new table added via a new migration; existing tables untouched
