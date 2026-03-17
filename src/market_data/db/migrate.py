"""Migration runner — executes DDL files from db/migrations_pg/ in alphabetical order."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from market_data.db.connection import get_connection

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations_pg"


def _exec_script(conn, sql: str) -> None:
    """Execute a multi-statement SQL script by splitting on semicolons.

    Single-line comments (``--`` to end of line) are stripped first so that
    semicolons inside comments do not cause spurious splits.
    """
    sql_stripped = re.sub(r"--[^\n]*", "", sql)
    for statement in sql_stripped.split(";"):
        stmt = statement.strip()
        if stmt:
            conn.execute(stmt)


def migrate() -> None:
    """Run all pending SQL migration files in order."""
    conn = get_connection()

    # Ensure TimescaleDB extension exists before running any migration.
    # This must be done by a superuser; if it fails, the admin must run:
    #   psql -U postgres -d <dbname> -c "CREATE EXTENSION timescaledb;"
    try:
        conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    except Exception as exc:
        logger.warning(
            "Could not auto-create TimescaleDB extension (%s). "
            "Run: psql -U postgres -d <dbname> -c \"CREATE EXTENSION timescaledb;\"",
            exc,
        )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            filename   TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    applied = {
        row[0] for row in conn.execute("SELECT filename FROM _migrations").fetchall()
    }

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        logger.info("No migration files found in %s", MIGRATIONS_DIR)
        return

    for path in migration_files:
        if path.name in applied:
            logger.debug("Skipping already-applied migration: %s", path.name)
            continue

        logger.info("Applying migration: %s", path.name)
        sql = path.read_text()
        _exec_script(conn, sql)
        conn.execute("INSERT INTO _migrations (filename) VALUES (%s)", [path.name])
        logger.info("Applied: %s", path.name)

    logger.info("All migrations up to date.")
