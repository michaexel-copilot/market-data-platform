"""DB helpers for scheduler_jobs table."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg2.extensions import connection as PgConnection


def load_job_states(conn: "PgConnection") -> dict[str, bool]:
    """Return {job_id: enabled} for every row in scheduler_jobs."""
    rows = conn.execute("SELECT job_id, enabled FROM scheduler_jobs").fetchall()
    return {row[0]: bool(row[1]) for row in rows}


def set_job_enabled(conn: "PgConnection", job_id: str, enabled: bool) -> None:
    """Flip the enabled flag for *job_id*.

    Raises ValueError if job_id is not found in scheduler_jobs.
    """
    result = conn.execute(
        "UPDATE scheduler_jobs SET enabled = %s, updated_at = now() WHERE job_id = %s",
        [enabled, job_id],
    )
    if result.rowcount == 0:
        raise ValueError(f"Unknown scheduler job: {job_id!r}")
