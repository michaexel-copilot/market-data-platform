# Scheduler Job Admin API

## Purpose

Defines the REST endpoints that allow operators to inspect and toggle scheduler jobs at runtime. Changes are persisted to the DB and applied live to the running APScheduler instance.

## Requirements

### Requirement: List scheduler jobs
The system SHALL expose `GET /v1/admin/scheduler/jobs` returning a JSON array of all known jobs. Each item SHALL include `job_id` (string), `enabled` (bool), and `next_run_time` (ISO 8601 UTC string or `null` if the scheduler is not running or the job is paused).

#### Scenario: All jobs running
- **WHEN** `GET /v1/admin/scheduler/jobs` is called while the scheduler is running and all jobs are enabled
- **THEN** the response is HTTP 200 with a JSON array of four objects, each having a non-null `next_run_time`

#### Scenario: One job paused
- **WHEN** a job has been disabled and the scheduler is running
- **THEN** that job's entry has `enabled: false` and `next_run_time: null`

#### Scenario: Scheduler not running
- **WHEN** `GET /v1/admin/scheduler/jobs` is called in a context where the scheduler reference is not available (e.g. a separate `serve` instance without the scheduler)
- **THEN** the response is HTTP 200 with `next_run_time: null` for all jobs; `enabled` reflects the DB state

---

### Requirement: Enable a scheduler job
The system SHALL expose `POST /v1/admin/scheduler/jobs/{job_id}/enable` that sets `enabled = true` in the `scheduler_jobs` table and, if the scheduler is running and the job is currently registered, calls `resume_job(job_id)`. If the job was never registered (started disabled), the endpoint SHALL call `add_job()` to register it fresh.

#### Scenario: Enable a paused job
- **WHEN** `POST /v1/admin/scheduler/jobs/ohlcv_1m/enable` is called while the scheduler is running and the job is paused
- **THEN** the response is HTTP 200; the job's `enabled` column is `true`; the job's `next_run_time` becomes non-null

#### Scenario: Enable a job that was never registered
- **WHEN** the service started with `ohlcv_1m` disabled and `POST /v1/admin/scheduler/jobs/ohlcv_1m/enable` is called
- **THEN** the response is HTTP 200; the job is registered in the running scheduler with its correct trigger; `next_run_time` is non-null

#### Scenario: Enable an already-enabled job is idempotent
- **WHEN** `POST /v1/admin/scheduler/jobs/ohlcv_1m/enable` is called on a job that is already enabled and running
- **THEN** the response is HTTP 200 with no error

#### Scenario: Enable unknown job returns 404
- **WHEN** `POST /v1/admin/scheduler/jobs/nonexistent/enable` is called
- **THEN** the response is HTTP 404

---

### Requirement: Disable a scheduler job
The system SHALL expose `POST /v1/admin/scheduler/jobs/{job_id}/disable` that sets `enabled = false` in the `scheduler_jobs` table and, if the scheduler is running and the job is registered, calls `pause_job(job_id)`. Pausing SHALL NOT interrupt a currently-executing job instance.

#### Scenario: Disable a running job
- **WHEN** `POST /v1/admin/scheduler/jobs/ohlcv_1m/disable` is called while the job is running normally
- **THEN** the response is HTTP 200; the job's `enabled` column is `false`; the job no longer fires new executions; any in-flight execution completes normally

#### Scenario: Disable an already-disabled job is idempotent
- **WHEN** `POST /v1/admin/scheduler/jobs/ohlcv_1m/disable` is called on a job that is already disabled
- **THEN** the response is HTTP 200 with no error

#### Scenario: Disable unknown job returns 404
- **WHEN** `POST /v1/admin/scheduler/jobs/nonexistent/disable` is called
- **THEN** the response is HTTP 404

---

### Requirement: Live scheduler reference
The system SHALL maintain a module-level reference to the active `AsyncIOScheduler` instance, accessible via `get_scheduler() -> AsyncIOScheduler | None`. It SHALL return `None` when no scheduler has been started. The reference SHALL be set immediately after `scheduler.start()` is called.

#### Scenario: Scheduler reference available after start
- **WHEN** the scheduler is started via `run_scheduler()` or the `serve` entry point
- **THEN** `get_scheduler()` returns the running scheduler instance

#### Scenario: Scheduler reference is None before start
- **WHEN** `get_scheduler()` is called before the scheduler has been started
- **THEN** `None` is returned
