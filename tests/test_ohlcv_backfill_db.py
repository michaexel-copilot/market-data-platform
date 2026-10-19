"""
Database tests for ohlcv_backfill.py against a real TimescaleDB with a copy of the
production schema (tests/fixtures/market_data_schema.sql).
Skipped unless TEST_DATABASE_URL points at a disposable server; each test creates
and drops its own database there, e.g.
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
DB = "backfill_test"


@pytest.fixture
def conn(monkeypatch):
    import psycopg

    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {DB}")
    test_url = URL.rsplit("/", 1)[0] + f"/{DB}"
    monkeypatch.setenv("DATABASE_URL", test_url)
    with psycopg.connect(test_url) as c:
        c.execute((ROOT / "tests" / "fixtures" / "market_data_schema.sql").read_text())
        c.commit()
    ob.cmd_init_views(None)
    ob.cmd_init_views(None)             # idempotent
    with ob.connect() as c:
        yield c


def _candles(start, n, step=timedelta(hours=1)):
    return [ob.Candle(start + i * step, 1, 2, 0.5, 1.5, 10, 3, 1.2) for i in range(n)]


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_upsert_fills_ticks_and_never_overwrites(conn):
    conn.execute("INSERT INTO ohlcv (instrument_id, interval, ts, open, high, low, close, source, tick_1h) "
                 "VALUES ('bitcoin', '1h', %s, 9, 9, 9, 9, 'eodhd', %s)", (T0, int(T0.timestamp()) // 3600))
    conn.commit()
    n, skipped = ob.upsert(conn, "bitcoin", "1h", "kraken", _candles(T0, 48), batch_size=10)
    assert (n, skipped) == (47, 0)                       # the eodhd candle stays
    assert ob.upsert(conn, "bitcoin", "1h", "kraken", _candles(T0, 48)) == (0, 0)

    first = conn.execute("SELECT source, close FROM ohlcv WHERE ts = %s", (T0,)).fetchone()
    assert first == ("eodhd", 9)
    tick = conn.execute("SELECT tick_1h FROM ohlcv WHERE ts = %s", (T0 + timedelta(hours=5),)).fetchone()[0]
    assert tick == int(T0.timestamp()) // 3600 + 5

    flags = conn.execute("SELECT has_1h, has_1d FROM ohlcv_data_available a JOIN data_source s "
                         "USING (data_source_id) WHERE short_name = 'kraken_hist'").fetchone()
    assert flags == (True, False)


def test_daily_and_minute_ticks(conn):
    ob.upsert(conn, "bitcoin", "1d", "kraken", _candles(T0, 3, timedelta(days=1)))
    ob.upsert(conn, "bitcoin", "1m", "okx", _candles(T0, 3, timedelta(minutes=1)))
    rows = conn.execute("SELECT interval, min(tick_1d), min(tick_1m) FROM ohlcv GROUP BY interval "
                        "ORDER BY interval").fetchall()
    assert rows == [("1d", int(T0.timestamp()) // 86400, None), ("1m", None, int(T0.timestamp()) // 60)]
    # okx has no data_source row, so nothing is flagged for it
    assert conn.execute("SELECT count(*) FROM ohlcv_data_available").fetchone()[0] == 1


def test_insane_candles_are_skipped_not_fatal(conn):
    bad = [ob.Candle(T0, 1, 0.9, 0.5, 1.5, 10), ob.Candle(T0 + timedelta(hours=1), 0, 1, 0, 1, 1)]
    n, skipped = ob.upsert(conn, "bitcoin", "1h", "okx", bad + _candles(T0 + timedelta(hours=2), 2))
    assert (n, skipped) == (2, 2)


def test_coverage_and_gap_views(conn):
    ob.upsert(conn, "bitcoin", "1h", "okx", _candles(T0, 48))
    ob.upsert(conn, "bitcoin", "1h", "okx", _candles(T0 + timedelta(hours=52), 4))
    cov = conn.execute("SELECT rows, fill_ratio FROM backfill_coverage").fetchone()
    assert cov[0] == 52 and float(cov[1]) == pytest.approx(52 / 56, abs=1e-3)
    assert conn.execute("SELECT gap FROM backfill_gaps").fetchall() == [(timedelta(hours=5),)]


def test_targets_skip_unknown_instruments(conn, capsys):
    assert ob._targets(conn, "bitcoin,solana", "okx") == [("bitcoin", "BTC-USDT")]
    assert "skip solana" in capsys.readouterr().err
