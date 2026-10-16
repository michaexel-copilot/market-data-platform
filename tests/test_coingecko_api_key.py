"""
Tests for the optional COINGECKO_API_KEY support (HED-137).

Covers cg_market.py, draw_chart.py and perf_data.py:
  - header "x-cg-demo-api-key" is sent on every CoinGecko call when the env
    var is set,
  - header is absent entirely when the env var is unset/empty (unchanged
    behaviour),
  - the key value never appears in any exception/error message.

Each module reads COINGECKO_API_KEY once at import time (same pattern as the
existing CMC_API_KEY), so every test reloads the module under a controlled
environment instead of relying on import order across the test session.
"""
import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEST_KEY = "test-dummy-key"


def _reload(module_name: str, monkeypatch: pytest.MonkeyPatch, key: str | None):
    if key is None:
        monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    else:
        monkeypatch.setenv("COINGECKO_API_KEY", key)
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def _fake_response(json_body: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# cg_market.py — fetch_cg_market
# ---------------------------------------------------------------------------

def test_cg_market_sends_header_when_key_set(monkeypatch, tmp_path):
    cg_market = _reload("cg_market", monkeypatch, TEST_KEY)
    monkeypatch.setattr(cg_market, "CACHE_DIR", tmp_path)
    monkeypatch.setitem(cg_market._CG_ID_MAP, "BTC", "bitcoin")

    with patch("cg_market.requests.get", return_value=_fake_response({"market_data": {}})) as mock_get:
        cg_market.fetch_cg_market("BTC")

    assert mock_get.call_args.kwargs["headers"] == {"x-cg-demo-api-key": TEST_KEY}


def test_cg_market_no_header_when_key_unset(monkeypatch, tmp_path):
    cg_market = _reload("cg_market", monkeypatch, None)
    monkeypatch.setattr(cg_market, "CACHE_DIR", tmp_path)
    monkeypatch.setitem(cg_market._CG_ID_MAP, "BTC", "bitcoin")

    with patch("cg_market.requests.get", return_value=_fake_response({"market_data": {}})) as mock_get:
        cg_market.fetch_cg_market("BTC")

    assert mock_get.call_args.kwargs["headers"] == {}
    assert "x-cg-demo-api-key" not in mock_get.call_args.kwargs["headers"]


def test_cg_market_error_message_excludes_key(monkeypatch, tmp_path, capsys):
    cg_market = _reload("cg_market", monkeypatch, TEST_KEY)
    monkeypatch.setattr(cg_market, "CACHE_DIR", tmp_path)
    monkeypatch.setitem(cg_market._CG_ID_MAP, "BTC", "bitcoin")

    with patch("cg_market.requests.get", side_effect=ConnectionError("boom")):
        result = cg_market.fetch_cg_market("BTC")

    assert result == {**cg_market._EMPTY}
    captured = capsys.readouterr()
    assert TEST_KEY not in captured.out
    assert TEST_KEY not in captured.err


# ---------------------------------------------------------------------------
# draw_chart.py — _fetch_from_coingecko
# ---------------------------------------------------------------------------

def test_draw_chart_sends_header_when_key_set(monkeypatch):
    draw_chart = _reload("draw_chart", monkeypatch, TEST_KEY)

    body = {"prices": [[1700000000000, 42000.0]]}
    with patch("draw_chart.requests.get", return_value=_fake_response(body)) as mock_get:
        draw_chart._fetch_from_coingecko("bitcoin")

    assert mock_get.call_args.kwargs["headers"] == {"x-cg-demo-api-key": TEST_KEY}


def test_draw_chart_no_header_when_key_unset(monkeypatch):
    draw_chart = _reload("draw_chart", monkeypatch, None)

    body = {"prices": [[1700000000000, 42000.0]]}
    with patch("draw_chart.requests.get", return_value=_fake_response(body)) as mock_get:
        draw_chart._fetch_from_coingecko("bitcoin")

    assert mock_get.call_args.kwargs["headers"] == {}


def test_draw_chart_error_message_excludes_key(monkeypatch, capsys):
    draw_chart = _reload("draw_chart", monkeypatch, TEST_KEY)

    with patch("draw_chart.requests.get", side_effect=ConnectionError("boom")), \
         pytest.raises(ConnectionError):
        draw_chart._fetch_from_coingecko("bitcoin")

    captured = capsys.readouterr()
    assert TEST_KEY not in captured.out
    assert TEST_KEY not in captured.err


# ---------------------------------------------------------------------------
# perf_data.py — _fetch_5y_cg / _fetch_hourly_cg
# ---------------------------------------------------------------------------

def test_perf_data_5y_sends_header_when_key_set(monkeypatch):
    perf_data = _reload("perf_data", monkeypatch, TEST_KEY)

    body = {"prices": [[1700000000000, 42000.0]], "total_volumes": []}
    with patch("perf_data.requests.get", return_value=_fake_response(body)) as mock_get:
        perf_data._fetch_5y_cg("bitcoin")

    assert mock_get.call_args.kwargs["headers"] == {"x-cg-demo-api-key": TEST_KEY}


def test_perf_data_5y_no_header_when_key_unset(monkeypatch):
    perf_data = _reload("perf_data", monkeypatch, None)

    body = {"prices": [[1700000000000, 42000.0]], "total_volumes": []}
    with patch("perf_data.requests.get", return_value=_fake_response(body)) as mock_get:
        perf_data._fetch_5y_cg("bitcoin")

    assert mock_get.call_args.kwargs["headers"] == {}


def test_perf_data_hourly_sends_header_when_key_set(monkeypatch):
    perf_data = _reload("perf_data", monkeypatch, TEST_KEY)

    body = {"prices": [[1700000000000, 42000.0]], "total_volumes": []}
    with patch("perf_data.requests.get", return_value=_fake_response(body)) as mock_get:
        perf_data._fetch_hourly_cg("bitcoin", 1.0)

    assert mock_get.call_args.kwargs["headers"] == {"x-cg-demo-api-key": TEST_KEY}


def test_perf_data_hourly_no_header_when_key_unset(monkeypatch):
    perf_data = _reload("perf_data", monkeypatch, None)

    body = {"prices": [[1700000000000, 42000.0]], "total_volumes": []}
    with patch("perf_data.requests.get", return_value=_fake_response(body)) as mock_get:
        perf_data._fetch_hourly_cg("bitcoin", 1.0)

    assert mock_get.call_args.kwargs["headers"] == {}


def test_perf_data_error_message_excludes_key(monkeypatch):
    perf_data = _reload("perf_data", monkeypatch, TEST_KEY)

    with patch("perf_data.requests.get", side_effect=ConnectionError("boom")), \
         pytest.raises(ConnectionError) as exc_info:
        perf_data._fetch_5y_cg("bitcoin")

    assert TEST_KEY not in str(exc_info.value)
