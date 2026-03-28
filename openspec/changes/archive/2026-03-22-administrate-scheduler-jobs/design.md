## Context

The ingestion scheduler runs four APScheduler jobs (`ohlcv_1m`, `ohlcv_5m`, `ohlcv_1h`, `ohlcv_1d`) that are registered unconditionally at startup. There is no mechanism to disable a job at runtime or across restarts without modifying source code. This design adds a PostgreSQL-backed toggle that persists across restarts and exposes it through the existing REST admin API and management console.

The service can run in two modes: as a standalone `uv run scheduler` process, or with the scheduler embedded in `uv run serve`. Both entry points must honour the same DB-backed configuration.

## Goals / Non-Goals

**Goals:**
- Persist enabled/disabled state in a `scheduler_jobs` DB table so it survives restarts
- Read the table at startup and skip `add_job()` for disabled jobs
- Expose a live scheduler reference so REST endpoints can pause/resume without a restart
- Three admin REST endpoints: list jobs, enable a job, disable a job
- Management console "Scheduler" panel with per-row toggle buttons

**Non-Goals:**
- Changing job schedules/triggers at runtime (only enabled state is mutable)
- Creating or deleting job definitions at runtime
- Per-instrument or per-connector job granularity
- Authentication / authorisation on the admin endpoints (out of scope for this change)

## Decisions

### D1 — DB table as source of truth (not env vars or config file)

Env vars would require a restart to take effect and cannot be changed from the UI. A DB table is writable at runtime, persists across restarts, is visible to any service instance, and fits the existing migration pattern. An in-memory toggle (APScheduler `pause_job` alone) would be lost on restart.

**Alternatives considered**: env var `DISABLE_OHLCV_1M=1` — simple but not runtime-mutable; Redis key — adds a dependency not otherwise present.

### D2 — `build_scheduler(enabled_jobs: set[str] | None = None)` parameter

Passing the enabled set as a parameter keeps `build_scheduler()` a pure factory function with no hidden DB access. The caller (the entry point, whether `run_scheduler()` or `serve()`) is responsible for loading the DB state before calling it. This makes the function testable without a DB.

`None` means "all enabled" — forward-compatible default so callers that don't pass the argument (e.g., tests) keep the current all-jobs behaviour.

**Alternatives considered**: have `build_scheduler()` accept a DB connection and read the table itself — mixes concerns; makes unit testing harder.

### D3 — Module-level `_scheduler` global + `get_scheduler()` accessor

The REST endpoints need access to the live `AsyncIOScheduler` instance to call `pause_job`/`resume_job`. Storing it in a module-level variable in `scheduler.py` is the simplest approach consistent with how FastAPI apps typically share in-process state (similar to how `get_connection()` works for the DB).

**Alternatives considered**: store on FastAPI `app.state` — would require access to the app object in the admin router, adding coupling; dependency injection via FastAPI `Depends` — over-engineered for a single scheduler instance.

### D4 — `pause_job`/`resume_job` for live toggling, not `remove_job`/`add_job`

`pause_job` preserves the job's trigger configuration in memory so `resume_job` can restart it without re-reading the DB. `remove_job` + `add_job` would require reconstructing the trigger, which duplicates logic from `build_scheduler()`.

The implication: if the service starts with a job disabled (never registered), a subsequent `/enable` call cannot use `resume_job` — it must call `add_job`. The implementation must handle this case: if `scheduler.get_job(job_id)` returns `None`, fall back to registering the job fresh. The mapping from `job_id` to `(func, trigger)` must therefore be accessible as a registry dict inside `scheduler.py`.

### D5 — `set_job_enabled` raises `ValueError` for unknown job IDs

Silent no-ops on unknown IDs would mask typos in API calls. A `ValueError` surfaces immediately and the REST endpoint converts it to HTTP 404.

### D6 — Management console: full-width `#PANE_SCHEDULER` hidden panel

Scheduler jobs are global (not instrument-scoped), so the existing two-pane layout (instrument list + content) does not apply. A dedicated full-width panel hidden by default and shown via a top-bar nav button is the least-invasive addition to the existing single-file HTML SPA in `console.py`.

## Risks / Trade-offs

- **Startup race**: if the scheduler starts before migrations run, the `scheduler_jobs` table won't exist. Mitigation: both entry points call `migrate()` before reading job states — this is the existing pattern.
- **Stale state on multi-instance deploy**: if two instances of `serve` run in parallel, one instance's live APScheduler state won't reflect a toggle made via the other. Mitigation: out of scope; documented as a known limitation. The DB state is always consistent; the live toggle only affects the instance that received the request.
- **`add_job` on enable of never-registered job**: requires a job registry dict inside `scheduler.py` mapping `job_id → (func, trigger_factory)`. Small amount of extra complexity but necessary for correctness.

## Migration Plan

1. Deploy new code — `migrate()` runs `029_scheduler_jobs.sql` on startup, seeding 4 jobs all enabled. No downtime.
2. To disable a job: `POST /v1/admin/scheduler/jobs/ohlcv_1m/disable` — takes effect immediately in the running process and persists across restarts.
3. Rollback: drop the migration by deleting `029_scheduler_jobs.sql` and rolling back the table manually. `build_scheduler()` called with `None` registers all jobs — no code change needed.

## Open Questions

- None — all decisions resolved above.
