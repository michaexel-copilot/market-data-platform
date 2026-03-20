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


def test_ohlcv_tick_1h_column_exists(db_conn):
    """ohlcv.tick_1h column must exist after migration 026."""
    row = db_conn.execute(
        """
        SELECT column_name, data_type
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name   = 'ohlcv'
           AND column_name  = 'tick_1h'
        """
    ).fetchone()
    assert row is not None, "Column tick_1h not found in ohlcv table"
    assert row[1] == "bigint", f"Expected bigint, got {row[1]}"


def test_ohlcv_tick_1h_backfill(db_conn):
    """No interval='1h' row may have tick_1h IS NULL after migration."""
    # Insert a 1h row the new way (via raw SQL, as the writer now does) and verify constraint.
    # Also verify the constraint prevents a NULL tick_1h on a 1h row.
    db_conn.execute(
        """
        INSERT INTO ohlcv
            (instrument_id, interval, ts, open, high, low, close, source, ingested_at, tick_1h)
        VALUES ('TEST-TICK', '1h', '2026-01-01T06:00:00Z', 1, 1, 1, 1, 'test', now(), 491334)
        """
    )
    row = db_conn.execute(
        "SELECT tick_1h FROM ohlcv WHERE instrument_id = 'TEST-TICK' AND interval = '1h'"
    ).fetchone()
    assert row is not None and row[0] == 491334, f"Expected tick_1h=491334, got {row}"

    # Verify the constraint rejects a 1h row with tick_1h = NULL
    with pytest.raises(Exception, match="ohlcv_tick_1h_not_null"):
        db_conn.execute(
            """
            INSERT INTO ohlcv
                (instrument_id, interval, ts, open, high, low, close, source, ingested_at, tick_1h)
            VALUES ('TEST-TICK-NULL', '1h', '2026-01-01T07:00:00Z', 1, 1, 1, 1, 'test', now(), NULL)
            """
        )


def test_ohlcv_tick_1d_column_exists(db_conn):
    """ohlcv.tick_1d column must exist after migration 027."""
    row = db_conn.execute(
        """
        SELECT column_name, data_type
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name   = 'ohlcv'
           AND column_name  = 'tick_1d'
        """
    ).fetchone()
    assert row is not None, "Column tick_1d not found in ohlcv table"
    assert row[1] == "bigint", f"Expected bigint, got {row[1]}"


def test_ohlcv_tick_1d_backfill(db_conn):
    """No interval='1d' row may have tick_1d IS NULL after migration."""
    # 2026-01-01T00:00:00Z → epoch = 1735689600 → tick_1d = 1735689600 // 86400 = 20089
    db_conn.execute(
        """
        INSERT INTO ohlcv
            (instrument_id, interval, ts, open, high, low, close, source, ingested_at, tick_1d)
        VALUES ('TEST-TICK-1D', '1d', '2026-01-01T00:00:00Z', 1, 1, 1, 1, 'test', now(), 20089)
        """
    )
    row = db_conn.execute(
        "SELECT tick_1d FROM ohlcv WHERE instrument_id = 'TEST-TICK-1D' AND interval = '1d'"
    ).fetchone()
    assert row is not None and row[0] == 20089, f"Expected tick_1d=20089, got {row}"

    # Verify the constraint rejects a 1d row with tick_1d = NULL
    with pytest.raises(Exception, match="ohlcv_tick_1d_not_null"):
        db_conn.execute(
            """
            INSERT INTO ohlcv
                (instrument_id, interval, ts, open, high, low, close, source, ingested_at, tick_1d)
            VALUES ('TEST-TICK-1D-NULL', '1d', '2026-01-02T00:00:00Z', 1, 1, 1, 1, 'test', now(), NULL)
            """
        )
