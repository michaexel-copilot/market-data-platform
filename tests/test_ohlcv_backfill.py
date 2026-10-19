"""
Tests for ohlcv_backfill.py: source parsers, file/page planning and pagination.
No network and no database: HTTP sessions are mocked.
"""
import sys
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

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


def test_kraken_members_and_parse():
    buf = BytesIO()
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


def test_symbol_map_seed_is_okx_and_kraken_only():
    symbols = ob.load_symbol_map()
    assert symbols["bitcoin"]["okx"] == "BTC-USDT"
    assert symbols["bitcoin"]["kraken"] == "XBTUSD"
    assert "binance" not in symbols["bitcoin"] and "hyperliquid" not in symbols["bitcoin"]
    assert "kraken" not in symbols["bnb"]   # bnb has no Kraken listing, cell stays empty
    assert ob._select(symbols, "bitcoin,ethereum", "okx") == [("bitcoin", "BTC-USDT"), ("ethereum", "ETH-USDT")]


# --- --intervals validation (HED-168: unvalidated interval reaches an f-string column
# name in mark_available(), a SQL injection path once a source using it has a data_source
# row) ---------------------------------------------------------------------------------

def test_update_rejects_unknown_interval(monkeypatch):
    monkeypatch.setattr(ob, "cmd_update", lambda args: pytest.fail("must not reach cmd_update"))
    with pytest.raises(SystemExit):
        ob.main(["update", "--intervals", "1h,bogus"])


def test_update_accepts_known_intervals(monkeypatch):
    captured = {}
    monkeypatch.setattr(ob, "cmd_update", lambda args: captured.setdefault("intervals", args.intervals))
    ob.main(["update", "--intervals", "1h,1d"])
    assert captured["intervals"] == ["1h", "1d"]


def test_update_default_intervals_parse_too():
    assert ob._interval_list("1h,1d") == ["1h", "1d"]


def test_kraken_rejects_unknown_interval(monkeypatch):
    monkeypatch.setattr(ob, "cmd_kraken", lambda args: pytest.fail("must not reach cmd_kraken"))
    with pytest.raises(SystemExit):
        ob.main(["kraken", "--zip", "x.zip", "--intervals", "1h,bogus"])


def test_kraken_accepts_known_intervals(monkeypatch):
    captured = {}
    monkeypatch.setattr(ob, "cmd_kraken", lambda args: captured.setdefault("intervals", args.intervals))
    ob.main(["kraken", "--zip", "x.zip", "--intervals", "1h,1d"])
    assert captured["intervals"] == ["1h", "1d"]
