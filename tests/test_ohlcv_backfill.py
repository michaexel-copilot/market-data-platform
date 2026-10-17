"""
Tests for ohlcv_backfill.py: source parsers, file/page planning and pagination.
No network and no database: HTTP sessions are mocked.
"""
import io
import sys
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ohlcv_backfill as ob  # noqa: E402

UTC = timezone.utc


def _resp(json_body=None, status_code=200, content=b""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.content = content
    resp.raise_for_status.return_value = None
    return resp


def test_binance_spot_csv_ms_and_us_timestamps():
    text = (
        "1502942400000,4261.48,4313.62,4261.32,4308.83,47.18,1502945999999,202366.13,171,35.16,150952.47,0\n"
        "1735689600000000,93576.0,94509.42,93489.03,94401.14,755.21,1735693199999999,71057150.0,104440,1,1,0\n"
    )
    c1, c2 = list(ob.parse_binance_kline_csv(text))
    assert c1.ts == datetime(2017, 8, 17, 4, tzinfo=UTC)
    assert c1.close == 4308.83 and c1.trade_count == 171
    assert abs(c1.vwap - 202366.13 / 47.18) < 1e-9
    assert c2.ts == datetime(2025, 1, 1, tzinfo=UTC)   # microseconds handled


def test_binance_futures_csv_skips_header():
    text = ("open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,"
            "taker_buy_quote_volume,ignore\n"
            "1577836800000,7189.43,7190.52,7170.15,7171.55,2449.049,1577840399999,17576436.3,3524,1,1,0\n")
    (c,) = ob.parse_binance_kline_csv(text)
    assert c.ts == datetime(2020, 1, 1, tzinfo=UTC)


def test_binance_file_stamps_monthly_then_daily():
    stamps = ob.binance_file_stamps(date(2026, 8, 15), date(2026, 10, 2))
    assert stamps == [("monthly", "2026-08"), ("monthly", "2026-09"),
                      ("daily", "2026-10-01"), ("daily", "2026-10-02")]


def test_binance_file_stamps_within_current_month():
    assert ob.binance_file_stamps(date(2026, 10, 15), date(2026, 10, 16)) == [
        ("daily", "2026-10-15"), ("daily", "2026-10-16")]


def test_fetch_binance_skips_missing_files():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("BTCUSDT-1d-2026-09.csv",
                    "1756684800000,1,2,0.5,1.5,10,1756771199999,15,3,0,0,0\n")
    session = MagicMock()
    session.get.side_effect = [_resp(status_code=404), _resp(content=buf.getvalue()), _resp(status_code=404)]
    candles = list(ob.fetch_binance("BTCUSDT", "1d", date(2026, 8, 1), date(2026, 10, 1), session=session))
    assert len(candles) == 1 and candles[0].close == 1.5
    urls = [call.args[0] for call in session.get.call_args_list]
    assert urls[0].endswith("/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2026-08.zip")
    assert urls[2].endswith("/spot/daily/klines/BTCUSDT/1d/BTCUSDT-1d-2026-10-01.zip")


def test_kraken_members_and_parse():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Kraken_OHLCVT/XBTUSD_60.csv", "1381095000,122.0,122.5,121.9,122.3,0.5,3\n")
        zf.writestr("Kraken_OHLCVT/XBTUSD_1440.csv", "1381017600,122.0,123,120,122.3,10,30\n")
        zf.writestr("Kraken_OHLCVT/XBTUSDT_60.csv", "")
        zf.writestr("Kraken_OHLCVT/XBTUSD_720.csv", "")
    with zipfile.ZipFile(buf) as zf:
        members = ob.kraken_members(zf, "XBTUSD")
        assert members == {"1h": "Kraken_OHLCVT/XBTUSD_60.csv", "1d": "Kraken_OHLCVT/XBTUSD_1440.csv"}
        (c,) = ob.parse_kraken_csv(zf.read(members["1h"]).decode())
    assert c.ts == datetime.fromtimestamp(1381095000, tz=UTC) and c.trade_count == 3


def test_okx_pages_backwards_and_drops_open_candle(monkeypatch):
    h = 3_600_000
    t0 = 1_700_000_000_000 - 1_700_000_000_000 % h
    page1 = [[str(t0 + 2 * h), "3", "3", "3", "3", "1", "1", "3", "0"],     # still open
             [str(t0 + h), "2", "2", "2", "2", "1", "1", "2", "1"]]
    page2 = [[str(t0), "1", "1", "1", "1", "2", "2", "2", "1"]]
    session = MagicMock()
    session.get.side_effect = [_resp({"code": "0", "data": page1}),
                               _resp({"code": "0", "data": page2}),
                               _resp({"code": "0", "data": []})]
    monkeypatch.setattr(ob.time, "sleep", lambda s: None)
    candles = list(ob.fetch_okx("BTC-USDT", "1h", ob._utc(t0 - h), ob._utc(t0 + 3 * h), session))
    assert [c.close for c in candles] == [2.0, 1.0]
    assert candles[1].vwap == 1.0
    afters = [call.kwargs["params"]["after"] for call in session.get.call_args_list]
    assert afters[1] == t0 + h and afters[2] == t0
    assert session.get.call_args_list[0].kwargs["params"]["bar"] == "1H"


def test_hyperliquid_paginates_forward_and_drops_open_candle():
    h = 3_600_000
    t0 = 1_700_000_000_000 - 1_700_000_000_000 % h
    row = lambda t: {"t": t, "T": t + h - 1, "s": "BTC", "i": "1h",  # noqa: E731
                     "o": "1", "h": "2", "l": "0.5", "c": "1.5", "v": "10", "n": 7}
    session = MagicMock()
    session.post.side_effect = [_resp([row(t0), row(t0 + h)]), _resp([row(t0 + 2 * h)])]
    candles = list(ob.fetch_hyperliquid("BTC", "1h", ob._utc(t0), ob._utc(t0 + 3 * h), session))
    assert [c.ts for c in candles] == [ob._utc(t0), ob._utc(t0 + h), ob._utc(t0 + 2 * h)]
    second = session.post.call_args_list[1].kwargs["json"]["req"]
    assert second["startTime"] == t0 + 2 * h


def test_hyperliquid_open_candle_excluded():
    now = 1_700_000_000_000
    rows = [{"t": now - 10, "T": now + 100, "o": "1", "h": "1", "l": "1", "c": "1", "v": "1", "n": 1}]
    assert list(ob.parse_hl_candles(rows, now)) == []


def test_symbol_map_seed_is_consistent():
    symbols = ob.load_symbol_map()
    assert symbols["bitcoin"]["kraken"] == "XBTUSD"
    assert "kraken" not in symbols["bnb"]
    assert ob._select(symbols, "bitcoin,ethereum", "okx") == [("bitcoin", "BTC-USDT"), ("ethereum", "ETH-USDT")]
