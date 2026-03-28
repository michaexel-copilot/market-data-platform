## 1. Database Migration

- [x] 1.1 Confirm highest existing migration number in `src/market_data/db/migrations_pg/` to determine correct sequence number
- [x] 1.2 Create `src/market_data/db/migrations_pg/029_scheduler_jobs.sql` with `scheduler_jobs` table (`job_id TEXT PK`, `enabled BOOL NOT NULL DEFAULT true`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`)
- [x] 1.3 Add `INSERT` seed rows for all four jobs (`ohlcv_1m`, `ohlcv_5m`, `ohlcv_1h`, `ohlcv_1d`) all with `enabled = true` — use `ON CONFLICT DO NOTHING` for idempotency

## 2. DB Helper Module

- [x] 2.1 Create `src/market_data/db/scheduler_jobs.py`
- [x] 2.2 Implement `load_job_states(db) -> dict[str, bool]` — SELECT all rows, return mapping; caller defaults missing keys to `True`
- [x] 2.3 Implement `set_job_enabled(db, job_id: str, enabled: bool) -> None` — UPDATE `enabled` and `updated_at`; raise `ValueError` if no row was updated (unknown `job_id`)

## 3. Scheduler Module Changes

- [x] 3.1 Add internal job registry dict in `scheduler.py` mapping `job_id → (func, trigger_factory)` for all four jobs
- [x] 3.2 Add `enabled_jobs: set[str] | None = None` parameter to `build_scheduler()`; skip `add_job()` for ids not in `enabled_jobs` (skip none when `None`)
- [x] 3.3 Add module-level `_scheduler: AsyncIOScheduler | None = None` variable
- [x] 3.4 Add `get_scheduler() -> AsyncIOScheduler | None` accessor function
- [x] 3.5 Set `_scheduler` in `_run_async()` immediately after `scheduler.start()`
- [x] 3.6 Update `run_scheduler()` to open a DB connection, call `load_job_states()`, and pass the enabled set into `build_scheduler()`

## 4. REST Admin Endpoints

- [x] 4.1 Add `GET /v1/admin/scheduler/jobs` endpoint in `src/market_data/api/rest/admin.py` — read all jobs from DB, merge with live `next_run_time` from `get_scheduler()` (null if scheduler not available or job paused), return JSON list
- [x] 4.2 Add `POST /v1/admin/scheduler/jobs/{job_id}/enable` — call `set_job_enabled(db, job_id, True)`; if scheduler running and job is registered call `resume_job(job_id)`; if not registered call `add_job()` using the job registry; return 404 on `ValueError`
- [x] 4.3 Add `POST /v1/admin/scheduler/jobs/{job_id}/disable` — call `set_job_enabled(db, job_id, False)`; if scheduler running and job is registered call `pause_job(job_id)`; return 404 on `ValueError`

## 5. API Server Wire-Up

- [x] 5.1 In `src/market_data/api/__init__.py` `_graceful_shutdown()`: replace broken `build_scheduler` import stub with proper `get_scheduler()` call to shut down in-process scheduler
- [x] 5.2 Scheduler state is loaded from DB inside `_run_async()` (scheduler entry point); REST serve path reads from DB on each API call

## 6. Management Console UI

- [x] 6.1 In `src/market_data/api/rest/console.py` `_CONSOLE_HTML`: add `<button id="BTN_NAV_SCHEDULER">Scheduler</button>` to the top bar inside `#NAV_TABS`
- [x] 6.2 Add `<div id="PANE_SCHEDULER">` containing `<h2>Scheduler Jobs</h2>` and `<table id="SCHED_TABLE">` with columns: Job ID, Status, Action
- [x] 6.3 Add JS: clicking `BTN_NAV_SCHEDULER` hides instrument list + fundamentals pane + action bar + filter controls, shows `#PANE_SCHEDULER`, fetches `GET /v1/admin/scheduler/jobs` and renders rows using `escHtml()`
- [x] 6.4 Add JS: clicking `BTN_NAV_INSTRUMENTS` restores the two-pane layout and hides `#PANE_SCHEDULER`
- [x] 6.5 Add JS: per-row toggle button calls `/enable` or `/disable`; disables button during request; on success re-fetches and re-renders; on error shows status message in `#SCHED_STATUS`

## 7. Verification

- [ ] 7.1 Run `uv run migrate` — confirm `scheduler_jobs` table exists with exactly 4 rows all enabled
- [ ] 7.2 `POST /v1/admin/scheduler/jobs/ohlcv_1m/disable` → `GET /v1/admin/scheduler/jobs` — confirm `ohlcv_1m` shows `enabled: false`
- [ ] 7.3 Restart the scheduler — confirm `ohlcv_1m` is absent from APScheduler's job list
- [ ] 7.4 `POST /v1/admin/scheduler/jobs/ohlcv_1m/enable` — confirm `ohlcv_1m` is enabled again
- [ ] 7.5 `POST /v1/admin/scheduler/jobs/nonexistent/disable` — confirm HTTP 404
- [ ] 7.6 Open `/console` → click "Scheduler" → confirm table shows 4 rows; disable a job; confirm row updates immediately
- [ ] 7.7 Run `uv run pytest` — confirm no regressions
