"""Tests for the ?sources= filter on GET /v1/instruments and import-source-intersection CLI."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    from market_data.api.rest.app import create_app
    return create_app()


@pytest.fixture(autouse=True)
def seed_intersection(db_conn):
    """Seed two instruments, populate source-intersection rows, auto-rollback."""
    db_conn.execute(
        "INSERT INTO instruments (instrument_id, ticker, exchange, asset_class, is_active)"
        " VALUES (%s,%s,%s,%s,%s)",
        ("uuid-btc-src", "BTC", "BINANCE", "crypto", True),
    )
    db_conn.execute(
        "INSERT INTO instruments (instrument_id, ticker, exchange, asset_class, is_active)"
        " VALUES (%s,%s,%s,%s,%s)",
        ("uuid-eth-src", "ETH", "BINANCE", "crypto", True),
    )
    # BTC is in both eodhd and hl; ETH is only in eodhd
    db_conn.execute(
        "INSERT INTO instrument_source_intersection (instrument_id, source_short_name)"
        " VALUES (%s,%s),(%s,%s),(%s,%s)",
        ("uuid-btc-src", "eodhd", "uuid-btc-src", "hl", "uuid-eth-src", "eodhd"),
    )
    yield db_conn


# ── API tests ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sources_omitted_returns_all(app):
    """No ?sources= parameter → existing behaviour, both instruments returned."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/instruments?asset_class=crypto")
    assert resp.status_code == 200
    tickers = {i["ticker"] for i in resp.json()["items"]}
    assert {"BTC", "ETH"}.issubset(tickers)


@pytest.mark.asyncio
async def test_sources_single_filter(app):
    """?sources=eodhd → both BTC and ETH (both in eodhd)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/instruments?asset_class=crypto&sources=eodhd")
    assert resp.status_code == 200
    tickers = {i["ticker"] for i in resp.json()["items"]}
    assert "BTC" in tickers
    assert "ETH" in tickers


@pytest.mark.asyncio
async def test_sources_intersection_two(app):
    """?sources=eodhd,hl → only BTC (intersection); ETH not in hl, excluded."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/instruments?asset_class=crypto&sources=eodhd,hl")
    assert resp.status_code == 200
    data = resp.json()
    tickers = {i["ticker"] for i in data["items"]}
    assert "BTC" in tickers
    assert "ETH" not in tickers


@pytest.mark.asyncio
async def test_sources_unknown_returns_empty(app):
    """?sources=nonexistent → empty result, no error."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/instruments?sources=nonexistent")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ── CLI unit tests ────────────────────────────────────────────────────────────

def test_import_source_intersection_missing_csv(tmp_path, monkeypatch):
    """CLI exits with code 1 when the CSV file does not exist."""
    import sys
    from pathlib import Path

    monkeypatch.setattr(
        "market_data.cli.import_source_intersection.CSV_PATH",
        tmp_path / "missing.csv",
    )

    from market_data.cli.import_source_intersection import main
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_import_source_intersection_matched(tmp_path, db_conn, monkeypatch):
    """CLI inserts eodhd + hl rows for matched tickers, skips unmatched ones."""
    import csv
    from pathlib import Path

    csv_file = tmp_path / "cc_hl_intersection.csv"
    with csv_file.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["base", "eodhd_code", "hl_symbol"])
        writer.writeheader()
        writer.writerow({"base": "BTC", "eodhd_code": "BTC-USD", "hl_symbol": "BTC/USDC:USDC"})
        writer.writerow({"base": "UNKNOWN_XXX", "eodhd_code": "", "hl_symbol": ""})

    monkeypatch.setattr(
        "market_data.cli.import_source_intersection.CSV_PATH",
        csv_file,
    )
    # Patch get_connection to use the test DB connection
    monkeypatch.setattr(
        "market_data.cli.import_source_intersection.get_connection",
        lambda: db_conn,
        raising=False,
    )
    # Ensure BTC instrument exists (may already be from session fixture)
    db_conn.execute(
        "INSERT INTO instruments (instrument_id, ticker, exchange, asset_class, is_active)"
        " VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        ("uuid-btc-cli", "BTC", "CLI_TEST", "crypto", True),
    )

    from importlib import import_module, reload
    import market_data.cli.import_source_intersection as mod
    reload(mod)
    mod.CSV_PATH = csv_file
    mod.get_connection = lambda: db_conn  # type: ignore[assignment]

    import io
    from contextlib import redirect_stdout
    out = io.StringIO()
    with redirect_stdout(out):
        mod.main()

    summary = out.getvalue()
    assert "matched=1" in summary
    assert "skipped=1" in summary

    rows = db_conn.execute(
        "SELECT source_short_name FROM instrument_source_intersection"
        " WHERE instrument_id = 'uuid-btc-cli' ORDER BY source_short_name"
    ).fetchall()
    sources = {r[0] for r in rows}
    assert sources == {"eodhd", "hl"}
