"""
Database tests for ohlcv_backfill.py against a real TimescaleDB.
Skipped unless TEST_DATABASE_URL points at a disposable database, e.g.
  docker run -d -e POSTGRES_PASSWORD=pw -p 55432:5432 timescale/timescaledb:latest-pg16
  TEST_DATABASE_URL=postgresql://postgres:pw@127.0.0.1:55432/postgres uv run pytest
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ohlcv_backfill as ob  # noqa: E402

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("OHLCV_TABLE", "ohlcv_test")
    with ob.connect() as c:
        c.execute("DROP MATERIALIZED VIEW IF EXISTS ohlcv_test_1d_from_1h CASCADE")
        c.execute("DROP TABLE IF EXISTS ohlcv_test CASCADE")
        c.commit()
    ob.cmd_init_schema(None)
    ob.cmd_init_schema(None)            # idempotent
    with ob.connect() as c:
        yield c


def _candles(start, n, step=timedelta(hours=1)):
    return [ob.Candle(start + i * step, 1, 2, 0.5, 1.5, 10, 3, 1.2) for i in range(n)]


def test_upsert_is_idempotent_and_views_work(conn):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = _candles(t0, 48)
    assert ob.upsert(conn, "bitcoin", "1h", "binance", rows, batch_size=10) == 48
    assert ob.upsert(conn, "bitcoin", "1h", "binance", rows) == 0
    # a hole: hours 48..51 missing
    assert ob.upsert(conn, "bitcoin", "1h", "binance", _candles(t0 + timedelta(hours=52), 4)) == 4

    cov = conn.execute("SELECT rows, fill_ratio FROM ohlcv_test_coverage").fetchone()
    assert cov[0] == 52 and float(cov[1]) == pytest.approx(52 / 56, abs=1e-3)

    gaps = conn.execute("SELECT gap FROM ohlcv_test_gaps").fetchall()
    assert gaps == [(timedelta(hours=5),)]

    conn.commit()
    conn.autocommit = True
    conn.execute("CALL refresh_continuous_aggregate('ohlcv_test_1d_from_1h', NULL, NULL)")
    daily = conn.execute("SELECT ts, hours, volume FROM ohlcv_test_1d_from_1h ORDER BY ts").fetchall()
    assert [(d[1], d[2]) for d in daily] == [(24, 240), (24, 240), (4, 40)]
