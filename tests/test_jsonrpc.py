"""Tests for JSON-RPC 2.0 handler."""
from __future__ import annotations

import json
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture(autouse=True)
def patched_db(db_conn):
    """Seed base test data for every JSON-RPC test; auto-rollback via db_conn."""
    db_conn.execute(
        "INSERT INTO instruments (instrument_id, ticker, exchange, asset_class, is_active)"
        " VALUES (%s, %s, %s, %s, %s)",
        ("uuid-btc-001", "BTC", "BINANCE", "crypto", True),
    )
    yield db_conn


@pytest.fixture
def app():
    from market_data.api.rest.app import create_app
    return create_app()


@pytest.mark.asyncio
async def test_valid_call(app):
    payload = {"jsonrpc": "2.0", "method": "instruments.list", "params": {}, "id": 1}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/jsonrpc", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert "result" in data


@pytest.mark.asyncio
async def test_unknown_method(app):
    payload = {"jsonrpc": "2.0", "method": "nonexistent.method", "params": {}, "id": 2}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/jsonrpc", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_invalid_params(app):
    # ohlcv.get without required 'symbol'
    payload = {"jsonrpc": "2.0", "method": "ohlcv.get", "params": {"interval": "1d"}, "id": 3}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/jsonrpc", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_batch_call(app):
    batch = [
        {"jsonrpc": "2.0", "method": "instruments.list", "params": {}, "id": 1},
        {"jsonrpc": "2.0", "method": "nonexistent.method", "params": {}, "id": 2},
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/jsonrpc", json=batch)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    ids = {item["id"] for item in data}
    assert ids == {1, 2}
    # First should succeed, second should have method not found error
    by_id = {item["id"]: item for item in data}
    assert "result" in by_id[1]
    assert by_id[2]["error"]["code"] == -32601
