# Plan: Scheduler Job Enable/Disable via DB Table

The `scheduler_jobs` PostgreSQL table becomes the source of truth for job activation. At startup `build_scheduler()` reads it and only registers enabled jobs. REST endpoints toggle jobs at runtime (DB-persisted + applied live via APScheduler's `pause_job`/`resume_job`).

---

## Phase 1 — Database

1. Create migration `src/market_data/db/migrations_pg/029_scheduler_jobs.sql`
   - Table: `scheduler_jobs(job_id TEXT PK, enabled BOOL NOT NULL DEFAULT true, updated_at TIMESTAMPTZ DEFAULT now())`
   - Seed all 4 known jobs (`ohlcv_1m`, `ohlcv_5m`, `ohlcv_1h`, `ohlcv_1d`) with `enabled = true`

2. Create `src/market_data/db/scheduler_jobs.py`
   - `load_job_states(db) -> dict[str, bool]` — SELECT all rows; missing job_id defaults to `True`
   - `set_job_enabled(db, job_id: str, enabled: bool) -> None` — UPDATE + set `updated_at = now()`; raise `ValueError` for unknown job IDs

## Phase 2 — Scheduler Changes

3. Modify `build_scheduler()` in `src/market_data/ingestion/scheduler.py`
   - Add `enabled_jobs: set[str] | None = None` parameter (None = register all)
   - Skip `add_job()` for jobs not in `enabled_jobs`

4. Expose a module-level `_scheduler: AsyncIOScheduler | None = None` + `get_scheduler()` accessor in the same file
   - Set `_scheduler` in `_run_async()` after `.start()` and in `api/__init__.py` startup (*parallel with step 5*)

## Phase 3 — REST Endpoints

5. Add 3 endpoints to `src/market_data/api/rest/admin.py` (*parallel with step 4*)
   - `GET /v1/admin/scheduler/jobs` — returns `[{job_id, enabled, next_run_time}]`; `next_run_time` pulled from live scheduler if available, else `null`
   - `POST /v1/admin/scheduler/jobs/{job_id}/enable` — persists to DB + calls `scheduler.resume_job()`
   - `POST /v1/admin/scheduler/jobs/{job_id}/disable` — persists to DB + calls `scheduler.pause_job()`

## Phase 4 — Wire-Up

6. Modify `src/market_data/api/__init__.py` — before `build_scheduler()`, call `load_job_states(db)` and pass the enabled set in; store the returned scheduler via the module-level global (*depends on steps 2, 3, 4*)

7. Modify `run_scheduler()` in `src/market_data/ingestion/scheduler.py` — after `migrate()`, open a DB connection, call `load_job_states()`, pass into `build_scheduler()` (*depends on steps 2, 3*)

## Phase 5 — Management Console GUI

The console is a single-page HTML SPA embedded in `_CONSOLE_HTML` (`src/market_data/api/rest/console.py`). Scheduler jobs are not instrument-scoped, so a top-bar nav button is the right approach — it replaces the instrument/content panes with a dedicated full-width scheduler view.

8. **Top-bar nav button** in `_CONSOLE_HTML`
   - Add `<button id="BTN_NAV_SCHEDULER">⚙ Scheduler</button>` to the top bar alongside the asset-class segment buttons
   - Clicking it hides `#PANE_INSTRUMENT_LIST` + `#PANE_CONTENT` and shows `#PANE_SCHEDULER`
   - Clicking any asset-class button hides `#PANE_SCHEDULER` and restores the normal two-pane layout

9. **`#PANE_SCHEDULER` HTML** — full-width div containing:
   - `<h2>Scheduler Jobs</h2>` heading
   - `<table id="TBL_SCHEDULER_JOBS">` with columns: Job ID | Trigger | Enabled | Next Run | Action
   - Initially hidden; populated on first nav click

10. **JS — load & render** — on `BTN_NAV_SCHEDULER` click:
    - `GET /v1/admin/scheduler/jobs` → array of `{job_id, enabled, next_run_time}`
    - Build table rows using existing `escHtml()` helper (XSS-safe)
    - Action column: single toggle button per row labelled "Disable" or "Enable" based on current state

11. **JS — toggle handler** — on toggle button click, follows existing `btnOhlcv` pattern:
    - Disable button + change label to "…" during request
    - POST to `/v1/admin/scheduler/jobs/{job_id}/enable` or `.../disable`
    - On success: re-fetch job list and re-render the full table
    - On error: show inline `<p class="error">` message inside `#PANE_SCHEDULER`

---

## Relevant Files

- `src/market_data/db/migrations_pg/029_scheduler_jobs.sql` — new migration
- `src/market_data/db/scheduler_jobs.py` — new DB helper
- `src/market_data/ingestion/scheduler.py` — modify `build_scheduler()`, add global + accessor, update `run_scheduler()`
- `src/market_data/api/rest/admin.py` — 3 new endpoints
- `src/market_data/api/__init__.py` — load state, store scheduler ref
- `src/market_data/api/rest/console.py` — add nav button, `#PANE_SCHEDULER` HTML, JS load/render/toggle

---

## Verification

1. Run `uv run migrate` — confirm `scheduler_jobs` table has 4 rows
2. `POST /v1/admin/scheduler/jobs/ohlcv_1m/disable` → `GET /v1/admin/scheduler/jobs` shows `enabled: false`
3. Restart service — confirm disabled job is absent from APScheduler's job list
4. Re-enable via REST — `next_run_time` becomes non-null in response
5. Open `/console` → click "⚙ Scheduler" → table shows 4 jobs; disable one → row updates immediately
6. `uv run pytest` — no regressions

---

## Decisions

- Missing job IDs in the table default to `enabled=True` (forward-compat, safe)
- `pause_job`/`resume_job` don't interrupt an already-running instance — acceptable behaviour
- Scheduler pane is full-width (hides instrument list) — jobs are global, not instrument-scoped
- `set_job_enabled` raises `ValueError` for unknown job IDs to prevent silent typos

---

## Further Considerations

1. **Migration number**: 28 migrations currently exist (`001`–`028`), so `029` is assumed. Should be verified before implementation starts.
