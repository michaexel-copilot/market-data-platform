"""CLI tests for compute-indicators — mocks httpx to avoid requiring a live server."""
from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Subprocess-based smoke tests (no server needed — these test argument parsing)
# ---------------------------------------------------------------------------

def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "compute-indicators", *args],
        capture_output=True,
        text=True,
    )


def test_help_exits_zero():
    result = _run("--help")
    assert result.returncode == 0
    assert "--strategy" in result.stdout


def test_missing_strategy_exits_nonzero():
    result = _run("--symbol", "BTC")
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# Unit tests — mock httpx to verify correct URL and payload construction
# ---------------------------------------------------------------------------

def _make_mock_response(status_code: int, json_body: dict) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.is_success = (200 <= status_code < 300)
    mock.json.return_value = json_body
    mock.text = str(json_body)
    return mock


def test_cli_posts_correct_payload_for_all_instruments(monkeypatch):
    """CLI builds the right request body when no --symbol is given."""
    from market_data.cli import compute_indicators

    mock_response = _make_mock_response(200, {
        "ok": 1, "errors": 0,
        "results": [{"ticker": "BTC", "status": "ok", "elapsed_s": 0.1}],
    })

    with patch("httpx.post", return_value=mock_response) as mock_post:
        with patch("sys.argv", ["compute-indicators", "--strategy", "best_sma"]):
            try:
                compute_indicators.main()
            except SystemExit as exc:
                assert exc.code == 0

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs[0][0].endswith("/v1/admin/compute-indicators")
    payload = call_kwargs[1]["json"]
    assert payload["strategy"] == "best_sma"
    assert "symbol" not in payload


def test_cli_includes_symbol_in_payload(monkeypatch):
    """CLI includes symbol when --symbol is provided."""
    from market_data.cli import compute_indicators

    mock_response = _make_mock_response(200, {
        "ok": 1, "errors": 0,
        "results": [{"ticker": "BTC", "status": "ok", "elapsed_s": 0.05}],
    })

    with patch("httpx.post", return_value=mock_response) as mock_post:
        with patch("sys.argv", ["compute-indicators", "--strategy", "best_sma", "--symbol", "BTC"]):
            try:
                compute_indicators.main()
            except SystemExit as exc:
                assert exc.code == 0

    payload = mock_post.call_args[1]["json"]
    assert payload["symbol"] == "BTC"


def test_cli_exits_1_on_errors_in_response(capsys):
    """CLI exits 1 when the response contains errors > 0."""
    from market_data.cli import compute_indicators

    mock_response = _make_mock_response(200, {
        "ok": 1, "errors": 1,
        "results": [
            {"ticker": "BTC", "status": "ok", "elapsed_s": 0.1},
            {"ticker": "ETH", "status": "error", "error": "no data", "elapsed_s": 0.0},
        ],
    })

    with patch("httpx.post", return_value=mock_response):
        with patch("sys.argv", ["compute-indicators", "--strategy", "best_sma"]):
            try:
                compute_indicators.main()
            except SystemExit as exc:
                assert exc.code == 1


def test_cli_exits_1_on_422(capsys):
    """CLI exits 1 when the server returns HTTP 422."""
    from market_data.cli import compute_indicators

    mock_response = _make_mock_response(422, {"detail": "Unknown strategy 'foo'. Available: best_sma"})

    with patch("httpx.post", return_value=mock_response):
        with patch("sys.argv", ["compute-indicators", "--strategy", "foo"]):
            try:
                compute_indicators.main()
            except SystemExit as exc:
                assert exc.code == 1


def test_cli_exits_1_on_connection_error(capsys):
    """CLI exits 1 when httpx raises a connection error."""
    import httpx
    from market_data.cli import compute_indicators

    with patch("httpx.post", side_effect=httpx.ConnectError("Connection refused")):
        with patch("sys.argv", ["compute-indicators", "--strategy", "best_sma"]):
            try:
                compute_indicators.main()
            except SystemExit as exc:
                assert exc.code == 1


def test_cli_respects_market_data_url_env(monkeypatch):
    """CLI reads MARKET_DATA_URL from environment."""
    from market_data.cli import compute_indicators

    mock_response = _make_mock_response(200, {"ok": 0, "errors": 0, "results": []})
    monkeypatch.setenv("MARKET_DATA_URL", "http://myserver:9999")

    with patch("httpx.post", return_value=mock_response) as mock_post:
        with patch("sys.argv", ["compute-indicators", "--strategy", "best_sma"]):
            try:
                compute_indicators.main()
            except SystemExit:
                pass

    url = mock_post.call_args[0][0]
    assert "myserver:9999" in url

