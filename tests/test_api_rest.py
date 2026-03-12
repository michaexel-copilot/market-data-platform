"""FastAPI integration tests using httpx.AsyncClient."""
from __future__ import annotations

import duckdb
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "market_data" / "db" / "migrations"


@pytest.fixture(autouse=True)
def patched_db():
    import market_data.db.connection as _mod
    original = _mod._conn
    conn = duckdb.connect(":memory:")
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.execute(f.read_text())
    conn.execute(
        """
        INSERT INTO instruments (instrument_id, ticker, exchange, asset_class, is_active)
        VALUES ('uuid-btc-001', 'BTC', 'BINANCE', 'crypto', TRUE)
        """
    )
    conn.execute(
        """
        INSERT INTO ohlcv (instrument_id, interval, ts, open, high, low, close, volume, source)
        VALUES ('uuid-btc-001', '1d', '2023-11-14 00:00:00+00', 35000, 36000, 34000, 35500, 1000, 'test')
        """
    )
    _mod._conn = conn
    yield conn
    conn.close()
    _mod._conn = original


@pytest.fixture
def app():
    from market_data.api.rest.app import create_app
    return create_app()


@pytest.mark.asyncio
async def test_list_instruments(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/instruments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(item["ticker"] == "BTC" for item in data["items"])


@pytest.mark.asyncio
async def test_get_instrument(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/instruments/uuid-btc-001")
    assert resp.status_code == 200
    assert resp.json()["ticker"] == "BTC"


@pytest.mark.asyncio
async def test_get_instrument_not_found(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/instruments/NONEXISTENT_XYZ")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_ohlcv(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/ohlcv/uuid-btc-001?interval=1d")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    bar = data["items"][0]
    assert bar["open"] == pytest.approx(35000)
    assert bar["close"] == pytest.approx(35500)
