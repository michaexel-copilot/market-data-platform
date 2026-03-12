"""Migration runner — executes DDL files from db/migrations/ in alphabetical order."""
from __future__ import annotations

import logging
from pathlib import Path

from market_data.db.connection import get_connection

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def migrate() -> None:
    """Run all pending SQL migration files in order."""
    conn = get_connection()

    # Create migrations tracking table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            filename   VARCHAR PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    applied = {row[0] for row in conn.execute("SELECT filename FROM _migrations").fetchall()}

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
        conn.execute(sql)
        conn.execute("INSERT INTO _migrations (filename) VALUES (?)", [path.name])
        logger.info("Applied: %s", path.name)

    logger.info("All migrations up to date.")
