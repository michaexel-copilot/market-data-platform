"""Integration tests for PostgreSQL migrations."""
from __future__ import annotations

import pytest


def _tables(db_conn) -> list[str]:
    return [
        r[0]
        for r in db_conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    ]


def _views(db_conn) -> list[str]:
    return [
        r[0]
        for r in db_conn.execute(
            "SELECT table_name FROM information_schema.views WHERE table_schema = 'public'"
        ).fetchall()
    ]


def test_all_migration_files_present():
    """Verify that the expected number of migration files exist on disk."""
    from pathlib import Path

    mdir = Path(__file__).parent.parent / "src" / "market_data" / "db" / "migrations_pg"
    sql_files = sorted(mdir.glob("*.sql"))
    assert len(sql_files) >= 17, f"Expected at least 17 migration files, got {len(sql_files)}"


def test_instruments_table_exists(db_conn):
    assert "instruments" in _tables(db_conn)


def test_ohlcv_table_exists(db_conn):
    assert "ohlcv" in _tables(db_conn)


def test_ohlcv_views_exist(db_conn):
    """ohlcv_weekly and ohlcv_monthly views (or continuous aggregates) must exist."""
    views = _views(db_conn)
    assert "ohlcv_weekly" in views, f"ohlcv_weekly not in views: {views}"
    assert "ohlcv_monthly" in views, f"ohlcv_monthly not in views: {views}"


def test_asset_class_tables_exist(db_conn):
    tables = _tables(db_conn)
    for expected in [
        "instrument_crypto",
        "instrument_equity",
        "instrument_etf",
        "instrument_fx",
        "instrument_commodity",
        "instrument_identifiers",
    ]:
        assert expected in tables, f"Missing table: {expected}"


def test_ohlcv_hypertable_if_timescaledb(db_conn):
    """When TimescaleDB is installed, ohlcv must be a hypertable."""
    row = db_conn.execute(
        "SELECT COUNT(*) FROM pg_available_extensions WHERE name = 'timescaledb'"
    ).fetchone()
    if not (row and row[0] > 0):
        pytest.skip("TimescaleDB extension not available on this PostgreSQL instance")
    row = db_conn.execute(
        "SELECT COUNT(*) FROM timescaledb_information.hypertables "
        "WHERE hypertable_name = 'ohlcv'"
    ).fetchone()
    assert row and row[0] == 1, "ohlcv is not a hypertable"
