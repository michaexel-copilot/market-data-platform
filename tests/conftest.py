"""Shared test fixtures."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

MIGRATIONS_PG_DIR = (
    Path(__file__).parent.parent / "src" / "market_data" / "db" / "migrations_pg"
)

# These migrations require the TimescaleDB extension; skipped in tests unless
# the extension is installed on the test PostgreSQL instance.
TIMESCALE_MIGRATIONS = frozenset(
    {
        "018_timescaledb_setup.sql",
        "019_ohlcv_hypertable.sql",
        "020_cmc_listing_snapshots_hypertable.sql",
        "021_ohlcv_continuous_aggregates.sql",
    }
)


def _exec_script(conn: psycopg.Connection, sql: str) -> None:
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)


def _has_timescaledb(conn: psycopg.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM pg_available_extensions WHERE name = 'timescaledb'"
    ).fetchone()
    return bool(row and row[0] > 0)


@pytest.fixture(scope="session")
def _pg_test_url() -> str:
    """Return the database URL for the test session.

    Reads ``TEST_DATABASE_URL`` first, then ``DATABASE_URL``.  Skips the
    entire session (all DB-dependent tests) when neither is set.
    """
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip(
            "Set DATABASE_URL (or TEST_DATABASE_URL) to run database integration tests"
        )
    return url


@pytest.fixture(scope="session")
def _apply_migrations(_pg_test_url: str) -> None:
    """Apply migrations_pg/ to the test database once per session."""
    with psycopg.connect(_pg_test_url, autocommit=True) as conn:
        has_ts = _has_timescaledb(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        applied = {
            r[0]
            for r in conn.execute("SELECT filename FROM _migrations").fetchall()
        }
        for sql_file in sorted(MIGRATIONS_PG_DIR.glob("*.sql")):
            if sql_file.name in applied:
                continue
            if sql_file.name in TIMESCALE_MIGRATIONS and not has_ts:
                continue
            _exec_script(conn, sql_file.read_text())
            conn.execute(
                "INSERT INTO _migrations (filename) VALUES (%s) ON CONFLICT DO NOTHING",
                [sql_file.name],
            )


@pytest.fixture
def db_conn(_pg_test_url: str, _apply_migrations: None):
    """Per-test psycopg3 connection.

    Runs in *autocommit=False* mode so every test's DML is automatically
    rolled back when the fixture tears down — giving the same clean-slate
    semantics that the old ``duckdb.connect(":memory:")`` fixtures provided.
    """
    import market_data.db.connection as _mod

    conn = psycopg.connect(_pg_test_url)  # autocommit=False → rollback on teardown
    original = _mod._conn
    _mod._conn = conn
    yield conn
    conn.rollback()
    _mod._conn = original
    conn.close()
