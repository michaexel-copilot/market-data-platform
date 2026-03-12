"""Integration tests for DuckDB migrations."""
from __future__ import annotations

import duckdb
import pytest
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "market_data" / "db" / "migrations"


@pytest.fixture
def fresh_conn():
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


def test_all_migrations_apply_without_error(fresh_conn):
    """All SQL migration files must execute successfully on a fresh DB."""
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    assert len(sql_files) >= 9, f"Expected at least 9 migration files, got {len(sql_files)}"
    for f in sql_files:
        fresh_conn.execute(f.read_text())


def test_instruments_table_exists(fresh_conn):
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        fresh_conn.execute(f.read_text())
    tables = [r[0] for r in fresh_conn.execute("SHOW TABLES").fetchall()]
    assert "instruments" in tables


def test_ohlcv_table_exists(fresh_conn):
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        fresh_conn.execute(f.read_text())
    tables = [r[0] for r in fresh_conn.execute("SHOW TABLES").fetchall()]
    assert "ohlcv" in tables


def test_ohlcv_views_exist(fresh_conn):
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        fresh_conn.execute(f.read_text())
    views = [
        r[0]
        for r in fresh_conn.execute(
            "SELECT table_name FROM information_schema.views"
        ).fetchall()
    ]
    assert "ohlcv_weekly" in views
    assert "ohlcv_monthly" in views


def test_asset_class_tables_exist(fresh_conn):
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        fresh_conn.execute(f.read_text())
    tables = [r[0] for r in fresh_conn.execute("SHOW TABLES").fetchall()]
    for expected in [
        "instrument_crypto",
        "instrument_equity",
        "instrument_etf",
        "instrument_fx",
        "instrument_commodity",
        "instrument_identifiers",
    ]:
        assert expected in tables, f"Missing table: {expected}"
