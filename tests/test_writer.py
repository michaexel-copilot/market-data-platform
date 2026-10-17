"""Unit tests for the OHLCV ingestion writer."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from market_data.models.ohlcv import OHLCVRecord


def _make_record(interval: str, ts: datetime) -> OHLCVRecord:
    return OHLCVRecord(
        instrument_id="TEST",
        interval=interval,
        ts=ts,
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.5,
        source="test",
    )


def _captured_rows(records: list[OHLCVRecord]) -> list[tuple]:
    """Call write_ohlcv with a mocked connection and return the rows passed to executemany."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    captured: list[tuple] = []

    def fake_executemany(sql, rows):
        captured.extend(rows)

    mock_cur.executemany = fake_executemany

    from market_data.ingestion import writer as writer_mod
    with patch.object(writer_mod, "get_connection", return_value=mock_conn):
        writer_mod.write_ohlcv(records)

    return captured


class TestAggregate1mTo1h:
    """Unit tests for the _aggregate_1m_to_1h helper function."""

    def _make_1m(self, ts, open_: float, high: float, low: float, close: float, volume: float = 1.0):
        from datetime import timezone

        return OHLCVRecord(
            instrument_id="TEST",
            interval="1m",
            ts=ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc),
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            source="binance",
        )

    def test_full_60_candle_hour_bucket(self):
        """60 1m candles for one complete hour aggregate to exactly 1 correct 1h candle."""
        import pytest
        from datetime import datetime, timedelta, timezone

        from market_data.api.rest.admin import _aggregate_1m_to_1h

        base_ts = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        records = [
            self._make_1m(
                ts=base_ts + timedelta(minutes=i),
                open_=100.0 + i * 0.1,
                high=101.0 + i * 0.1,
                low=99.0 + i * 0.1,
                close=100.5 + i * 0.1,
                volume=1.0,
            )
            for i in range(60)
        ]

        result = _aggregate_1m_to_1h("TEST", records)

        assert len(result) == 1
        h = result[0]
        assert h.ts == base_ts
        assert h.open == pytest.approx(100.0)             # first candle open
        assert h.high == pytest.approx(101.0 + 59 * 0.1) # max high
        assert h.low == pytest.approx(99.0)               # min low
        assert h.close == pytest.approx(100.5 + 59 * 0.1) # last candle close
        assert h.volume == pytest.approx(60.0)            # sum of all volumes
        assert h.is_aggregated is True
        assert h.source == "aggregated:binance_1m"

    def test_partial_bucket_mid_hour_cutoff(self):
        """Candles spanning only 43 minutes of an hour produce one partial 1h candle."""
        import pytest
        from datetime import datetime, timedelta, timezone

        from market_data.api.rest.admin import _aggregate_1m_to_1h

        base_ts = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        records = [
            self._make_1m(
                ts=base_ts + timedelta(minutes=i),
                open_=100.0,
                high=102.0,
                low=98.0,
                close=101.0,
                volume=1.0,
            )
            for i in range(43)  # 12:00 through 12:42
        ]

        result = _aggregate_1m_to_1h("TEST", records)

        assert len(result) == 1
        assert result[0].ts == base_ts
        assert result[0].volume == pytest.approx(43.0)
        assert result[0].open == pytest.approx(100.0)
        assert result[0].close == pytest.approx(101.0)

    def test_two_hour_buckets(self):
        """Records spanning two different hours produce two 1h candles."""
        from datetime import datetime, timedelta, timezone

        from market_data.api.rest.admin import _aggregate_1m_to_1h

        h1_ts = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        h2_ts = datetime(2024, 6, 15, 13, 0, 0, tzinfo=timezone.utc)
        records = [
            self._make_1m(h1_ts + timedelta(minutes=i), 100.0, 101.0, 99.0, 100.5)
            for i in range(5)
        ] + [
            self._make_1m(h2_ts + timedelta(minutes=i), 200.0, 201.0, 199.0, 200.5)
            for i in range(5)
        ]

        result = _aggregate_1m_to_1h("TEST", records)

        assert len(result) == 2
        assert result[0].ts == h1_ts
        assert result[1].ts == h2_ts


class TestWriterUpsertSemantics:
    """Integration tests verifying the CASE WHEN upsert semantics in write_ohlcv.

    Requires a real PostgreSQL connection (db_conn fixture).  Tests are
    skipped automatically when DATABASE_URL / TEST_DATABASE_URL is not set.
    """

    _INST_A = "test-upsert-agg-001"
    _INST_B = "test-upsert-real-001"

    def _seed_instrument(self, db_conn, instrument_id: str, ticker: str) -> None:
        db_conn.execute(
            "INSERT INTO instruments (instrument_id, ticker, exchange, asset_class, is_active)"
            " VALUES (%s, %s, 'TEST', 'crypto', TRUE)"
            " ON CONFLICT (instrument_id) DO NOTHING",
            [instrument_id, ticker],
        )

    def test_real_candle_overwrites_aggregated(self, db_conn):
        """A real candle (is_aggregated=False) must overwrite an existing aggregated row."""
        import pytest
        from datetime import datetime, timezone

        from market_data.ingestion.writer import write_ohlcv

        self._seed_instrument(db_conn, self._INST_A, "WTESTA")

        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        # Insert an aggregated row directly
        db_conn.execute(
            "INSERT INTO ohlcv"
            " (instrument_id, interval, ts, open, high, low, close, source, is_aggregated, tick_1m)"
            " VALUES (%s, '1m', %s, 100.0, 110.0, 90.0, 105.0, 'aggregated:binance_1m', TRUE, %s)",
            [self._INST_A, ts, int(ts.timestamp()) // 60],
        )

        # Upsert a real candle for the same primary key
        write_ohlcv([
            OHLCVRecord(
                instrument_id=self._INST_A,
                interval="1m",
                ts=ts,
                open=200.0,
                high=210.0,
                low=190.0,
                close=205.0,
                source="binance",
                is_aggregated=False,
            )
        ])

        row = db_conn.execute(
            "SELECT open, close, is_aggregated FROM ohlcv"
            " WHERE instrument_id = %s AND interval = '1m' AND ts = %s",
            [self._INST_A, ts],
        ).fetchone()
        assert row is not None
        assert row[0] == pytest.approx(200.0)   # real open overwrote aggregated
        assert row[1] == pytest.approx(205.0)   # real close overwrote aggregated
        assert row[2] is False                  # is_aggregated updated to False

    def test_aggregated_candle_does_not_overwrite_real(self, db_conn):
        """An aggregated candle (is_aggregated=True) must NOT overwrite a real row."""
        import pytest
        from datetime import datetime, timezone

        from market_data.ingestion.writer import write_ohlcv

        self._seed_instrument(db_conn, self._INST_B, "WTESTB")

        ts = datetime(2024, 1, 15, 11, 30, 0, tzinfo=timezone.utc)

        # Insert a real row directly
        db_conn.execute(
            "INSERT INTO ohlcv"
            " (instrument_id, interval, ts, open, high, low, close, source, is_aggregated, tick_1m)"
            " VALUES (%s, '1m', %s, 300.0, 310.0, 290.0, 305.0, 'binance', FALSE, %s)",
            [self._INST_B, ts, int(ts.timestamp()) // 60],
        )

        # Attempt to overwrite with an aggregated candle
        write_ohlcv([
            OHLCVRecord(
                instrument_id=self._INST_B,
                interval="1m",
                ts=ts,
                open=1.0,
                high=2.0,
                low=0.5,
                close=1.5,
                source="aggregated:binance_1m",
                is_aggregated=True,
            )
        ])

        row = db_conn.execute(
            "SELECT open, close, is_aggregated FROM ohlcv"
            " WHERE instrument_id = %s AND interval = '1m' AND ts = %s",
            [self._INST_B, ts],
        ).fetchone()
        assert row is not None
        assert row[0] == pytest.approx(300.0)   # real open preserved
        assert row[1] == pytest.approx(305.0)   # real close preserved
        assert row[2] is False                  # still False (real data wins)


class TestUpdateSourceSelection:
    def test_rejects_stale_lower_interval_data(self):
        from market_data.api.rest.instruments import _find_aggregation_source

        conn = MagicMock()
        target_last = datetime(2026, 4, 11, 6, 0, 0, tzinfo=timezone.utc)
        stale_5m = datetime(2026, 3, 22, 0, 55, 0, tzinfo=timezone.utc)
        conn.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=(target_last,))),
            MagicMock(fetchone=MagicMock(return_value=(stale_5m,))),
            MagicMock(fetchone=MagicMock(return_value=(None,))),
        ]

        source_interval, returned_target_last, source_last = _find_aggregation_source(conn, "TEST", "1h")

        assert source_interval is None
        assert returned_target_last == target_last
        assert source_last is None

    def test_prefers_closest_newer_source_interval(self):
        from market_data.api.rest.instruments import _find_aggregation_source

        conn = MagicMock()
        target_last = datetime(2026, 4, 11, 6, 0, 0, tzinfo=timezone.utc)
        newer_5m = datetime(2026, 4, 11, 6, 55, 0, tzinfo=timezone.utc)
        conn.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=(target_last,))),
            MagicMock(fetchone=MagicMock(return_value=(newer_5m,))),
        ]

        source_interval, returned_target_last, source_last = _find_aggregation_source(conn, "TEST", "1h")

        assert source_interval == "5m"
        assert returned_target_last == target_last
        assert source_last == newer_5m


class TestWriterTickColumn:
    def test_1m_record_produces_correct_tick_1m(self):
        ts = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        record = _make_record("1m", ts)
        rows = _captured_rows([record])
        assert len(rows) == 1
        tick_1m = rows[0][-4]
        expected = int(ts.timestamp()) // 60
        assert tick_1m == expected, f"Expected tick_1m={expected}, got {tick_1m}"

    def test_1h_record_produces_correct_tick_1h(self):
        # 2026-01-01 06:00:00 UTC → epoch = 1735714800 → tick = 1735714800 // 3600 = 482143
        ts = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        record = _make_record("1h", ts)
        rows = _captured_rows([record])
        assert len(rows) == 1
        tick_1h = rows[0][-3]
        expected = int(ts.timestamp()) // 3600
        assert tick_1h == expected, f"Expected tick_1h={expected}, got {tick_1h}"

    def test_1d_record_produces_correct_tick_1d(self):
        # 2026-01-01 00:00:00 UTC → epoch = 1735689600 → tick_1d = 1735689600 // 86400 = 20089
        ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        record = _make_record("1d", ts)
        rows = _captured_rows([record])
        assert len(rows) == 1
        tick_1d = rows[0][-2]
        expected = int(ts.timestamp()) // 86400
        assert tick_1d == expected, f"Expected tick_1d={expected}, got {tick_1d}"
        assert rows[0][-3] is None, "Expected tick_1h=None for 1d record"
        assert rows[0][-4] is None, "Expected tick_1m=None for 1d record"

    def test_non_1h_record_produces_null_tick_1h(self):
        ts = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        for interval in ("1m", "5m", "1d"):
            record = _make_record(interval, ts)
            rows = _captured_rows([record])
            assert len(rows) == 1
            tick_1h = rows[0][-3]
            assert tick_1h is None, f"Expected tick_1h=None for interval={interval}, got {tick_1h}"

    def test_non_1d_record_produces_null_tick_1d(self):
        ts = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        for interval in ("1m", "5m", "1h"):
            record = _make_record(interval, ts)
            rows = _captured_rows([record])
            assert len(rows) == 1
            tick_1d = rows[0][-2]
            assert tick_1d is None, f"Expected tick_1d=None for interval={interval}, got {tick_1d}"


class TestWriterSanityFiltering:
    def test_skips_zero_priced_records(self):
        ts = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        valid = _make_record("1h", ts)
        invalid = OHLCVRecord(
            instrument_id="TEST",
            interval="1h",
            ts=ts,
            open=0.0,
            high=1.0,
            low=0.0,
            close=1.0,
            source="test",
        )

        rows = _captured_rows([valid, invalid])

        assert len(rows) == 1
        assert rows[0][3] == 1.0
        assert rows[0][6] == 1.5

    def test_returns_zero_when_all_records_are_invalid(self):
        from market_data.ingestion import writer as writer_mod

        ts = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        invalid = OHLCVRecord(
            instrument_id="TEST",
            interval="1h",
            ts=ts,
            open=10.0,
            high=9.0,
            low=8.0,
            close=10.0,
            source="test",
        )

        with patch.object(writer_mod, "get_connection") as get_connection:
            written = writer_mod.write_ohlcv([invalid])

        assert written == 0
        get_connection.assert_not_called()
