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


class TestWriterTickColumn:
    def test_1h_record_produces_correct_tick_1h(self):
        # 2026-01-01 06:00:00 UTC → epoch = 1735714800 → tick = 1735714800 // 3600 = 482143
        ts = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        record = _make_record("1h", ts)
        rows = _captured_rows([record])
        assert len(rows) == 1
        tick_1h = rows[0][-2]  # second-to-last: tick_1h
        expected = int(ts.timestamp()) // 3600
        assert tick_1h == expected, f"Expected tick_1h={expected}, got {tick_1h}"

    def test_1d_record_produces_correct_tick_1d(self):
        # 2026-01-01 00:00:00 UTC → epoch = 1735689600 → tick_1d = 1735689600 // 86400 = 20089
        ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        record = _make_record("1d", ts)
        rows = _captured_rows([record])
        assert len(rows) == 1
        tick_1d = rows[0][-1]  # last: tick_1d
        expected = int(ts.timestamp()) // 86400
        assert tick_1d == expected, f"Expected tick_1d={expected}, got {tick_1d}"
        assert rows[0][-2] is None, "Expected tick_1h=None for 1d record"

    def test_non_1h_record_produces_null_tick_1h(self):
        ts = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        for interval in ("1m", "5m", "1d"):
            record = _make_record(interval, ts)
            rows = _captured_rows([record])
            assert len(rows) == 1
            tick_1h = rows[0][-2]
            assert tick_1h is None, f"Expected tick_1h=None for interval={interval}, got {tick_1h}"

    def test_non_1d_record_produces_null_tick_1d(self):
        ts = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        for interval in ("1m", "5m", "1h"):
            record = _make_record(interval, ts)
            rows = _captured_rows([record])
            assert len(rows) == 1
            tick_1d = rows[0][-1]
            assert tick_1d is None, f"Expected tick_1d=None for interval={interval}, got {tick_1d}"
