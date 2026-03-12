"""Shared test fixtures."""
from __future__ import annotations

import pytest
import duckdb


@pytest.fixture
def db_conn():
    """In-memory DuckDB connection with all migrations applied."""
    import os
    os.environ.setdefault("DUCKDB_PATH", ":memory:")
    # Patch get_connection to return a fresh in-memory conn for each test
    conn = duckdb.connect(":memory:")
    import market_data.db.connection as _conn_mod
    original = _conn_mod._conn
    _conn_mod._conn = conn
    # Run migrations
    from pathlib import Path
    migrations_dir = Path(__file__).parent.parent / "src" / "market_data" / "db" / "migrations"
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _migrations (
            name VARCHAR PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    for sql_file in sorted(migrations_dir.glob("*.sql")):
        sql = sql_file.read_text()
        conn.execute(sql)
    yield conn
    conn.close()
    _conn_mod._conn = original
