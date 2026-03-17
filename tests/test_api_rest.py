"""FastAPI integration tests using httpx.AsyncClient."""
from __future__ import annotations

import datetime
import random

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest.fixture(autouse=True)
def patched_db(db_conn):
    """Seed base test data for every REST API test; auto-rollback via db_conn."""
    db_conn.execute(
        "INSERT INTO instruments (instrument_id, ticker, exchange, asset_class, is_active)"
        " VALUES (%s, %s, %s, %s, %s)",
        ("uuid-btc-001", "BTC", "BINANCE", "crypto", True),
    )
    db_conn.execute(
        "INSERT INTO ohlcv"
        " (instrument_id, interval, ts, open, high, low, close, volume, source)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        ("uuid-btc-001", "1d", "2023-11-14 00:00:00+00", 35000, 36000, 34000, 35500, 1000, "test"),
    )
    yield db_conn


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


# ---------------------------------------------------------------------------
# Trading strategies endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_trading_strategies_404_when_no_data(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/trading-strategies/btc")
    assert resp.status_code == 404
    assert "precomputed" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_get_trading_strategies_symbol_not_found(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/trading-strategies/UNKNOWN_XYZ_999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_compute_missing_ohlcv(patched_db, app):
    # Remove OHLCV rows so compute fails with a missing-data error
    patched_db.execute("DELETE FROM ohlcv")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/trading-strategies/btc/compute", json={"strategy": "best_sma"})
    assert resp.status_code == 422
    assert "ohlcv" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_post_compute_unknown_strategy(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/trading-strategies/btc/compute", json={"strategy": "nonexistent"})
    assert resp.status_code == 422
    assert "unknown strategy" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_post_compute_then_get(patched_db, app):
    # Seed enough OHLCV rows for a meaningful backtest (200 days × 2 hourly rows)
    patched_db.execute("DELETE FROM ohlcv")
    rng = random.Random(99)
    price = 35000.0
    for i in range(200):
        day = datetime.date(2024, 1, 1) + datetime.timedelta(days=i)
        price *= 1 + rng.uniform(-0.03, 0.03)
        h, l = price * 1.01, price * 0.99
        for hour in (0, 23):
            ts = datetime.datetime.combine(day, datetime.time(hour, 0, 0))
            patched_db.execute(
                "INSERT INTO ohlcv"
                " (instrument_id, interval, ts, open, high, low, close, volume, source)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                ["uuid-btc-001", "1h", str(ts), price * 0.995, h, l, price, 500, "test"],
            )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # POST compute
        resp = await client.post("/v1/trading-strategies/btc/compute", json={"strategy": "best_sma"})
    assert resp.status_code == 200
    computed = resp.json()["computed"]
    names = {item["indicator_name"] for item in computed}
    assert "sma_low" in names
    assert "sma_high" in names

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # GET should now return 200
        resp = await client.get("/v1/trading-strategies/btc?strategy_name=best_sma")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Hyperliquid filter-assets tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_import_hl_pairs_endpoint(app, patched_db):
    """POST /v1/admin/import-hl-pairs should upsert HL pairs via the connector."""
    from unittest.mock import AsyncMock, patch
    from market_data.models.instrument import HLPairRecord

    fake_pairs = [
        HLPairRecord(hl_symbol="BTC/USDC:USDC", base_ticker="BTC", lot_size=1e-5, tick_size=0.0, max_leverage=50),
    ]

    with patch("market_data.connectors.hyperliquid.HyperliquidConnector.fetch_hl_pairs",
               new=AsyncMock(return_value=fake_pairs)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/v1/admin/import-hl-pairs", json={"network": "mainnet"})

    assert resp.status_code == 200
    data = resp.json()
    assert "upserted" in data
    assert "unmatched" in data
    assert "deactivated" in data
    assert data["upserted"] == 1
    assert data["unmatched"] == 0


@pytest.mark.asyncio
async def test_import_hl_pairs_invalid_network(app, patched_db):
    """POST /v1/admin/import-hl-pairs with invalid network should return 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/admin/import-hl-pairs", json={"network": "invalid"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_instruments_tradeable_on_hyperliquid_empty(app, patched_db):
    """GET /v1/instruments?tradeable_on=hyperliquid with no HL data returns empty."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/instruments?tradeable_on=hyperliquid")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_instruments_tradeable_on_hyperliquid_with_data(app, patched_db):
    """GET /v1/instruments?tradeable_on=hyperliquid returns instruments with HL metadata."""
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, patch
    from market_data.models.instrument import HLPairRecord

    fake_pairs = [
        HLPairRecord(hl_symbol="BTC/USDC:USDC", base_ticker="BTC", lot_size=1e-5, tick_size=0.0, max_leverage=50),
    ]

    # Seed HL data via the import endpoint
    with patch("market_data.connectors.hyperliquid.HyperliquidConnector.fetch_hl_pairs",
               new=AsyncMock(return_value=fake_pairs)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            import_resp = await client.post("/v1/admin/import-hl-pairs", json={"network": "mainnet"})
    assert import_resp.status_code == 200

    # Now filter by tradeable_on=hyperliquid
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/instruments?tradeable_on=hyperliquid&network=mainnet")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["ticker"] == "BTC"
    assert item.get("hyperliquid") is not None
    assert item["hyperliquid"]["hl_symbol"] == "BTC/USDC:USDC"
    assert item["hyperliquid"]["max_leverage"] == 50


@pytest.mark.asyncio
async def test_list_instruments_tradeable_on_invalid(app, patched_db):
    """GET /v1/instruments?tradeable_on=unknown should return 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/instruments?tradeable_on=unknown_exchange")
    assert resp.status_code == 400
