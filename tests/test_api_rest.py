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
        " (instrument_id, interval, ts, open, high, low, close, volume, source, tick_1d)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        ("uuid-btc-001", "1d", "2023-11-14 00:00:00+00", 35000, 36000, 34000, 35500, 1000, "test", 19675),
    )
    _ts1 = datetime.datetime(2023, 11, 14, 0, 0, 0, tzinfo=datetime.timezone.utc)
    _ts2 = datetime.datetime(2023, 11, 14, 23, 0, 0, tzinfo=datetime.timezone.utc)
    db_conn.execute(
        "INSERT INTO ohlcv"
        " (instrument_id, interval, ts, open, high, low, close, volume, source, tick_1h)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        ("uuid-btc-001", "1h", _ts1, 35000, 35500, 34900, 35200, 500, "test", int(_ts1.timestamp()) // 3600),
    )
    db_conn.execute(
        "INSERT INTO ohlcv"
        " (instrument_id, interval, ts, open, high, low, close, volume, source, tick_1h)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        ("uuid-btc-001", "1h", _ts2, 35200, 35800, 35100, 35600, 500, "test", int(_ts2.timestamp()) // 3600),
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


# ---------------------------------------------------------------------------
# Fundamentals endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_fundamentals_launch_date_present(patched_db, app):
    """launch_date is returned as YYYY-MM-DD when populated."""
    patched_db.execute(
        "UPDATE instruments SET launch_date = '2009-01-03' WHERE instrument_id = 'uuid-btc-001'"
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/instruments/uuid-btc-001/fundamentals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["launch_date"] == "2009-01-03"


@pytest.mark.asyncio
async def test_get_fundamentals_launch_date_absent(app):
    """launch_date is absent from the response when the column is NULL."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/instruments/uuid-btc-001/fundamentals")
    assert resp.status_code == 200
    data = resp.json()
    assert "launch_date" not in data


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
            tick_1h = int(ts.replace(tzinfo=datetime.timezone.utc).timestamp()) // 3600
            patched_db.execute(
                "INSERT INTO ohlcv"
                " (instrument_id, interval, ts, open, high, low, close, volume, source, tick_1h)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                ["uuid-btc-001", "1h", str(ts), price * 0.995, h, l, price, 500, "test", tick_1h],
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


@pytest.mark.asyncio
async def test_compute_v2_and_get_v2(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        compute_resp = await client.post(
            "/v1/trading-strategies/btc/compute-v2",
            json={"pos_usd": 120.0},
        )
    assert compute_resp.status_code == 200
    compute_data = compute_resp.json()
    assert compute_data["strategy"] == "best_sma_exit_v1"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_resp = await client.get("/v1/trading-strategies/btc/v2")
    assert get_resp.status_code == 200
    data = get_resp.json()
    indicator_names = {item["indicator_name"] for item in data["items"]}
    assert "sma_low" in indicator_names
    assert "sma_high" in indicator_names


@pytest.mark.asyncio
async def test_backtest_v2(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/trading-strategies/btc/backtest-v2",
            json={"pos_usd": 100.0, "max_trades": 50},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategy"] == "best_sma_exit_v1"
    assert "summary" in data
    assert "trades" in data


@pytest.mark.asyncio
async def test_admin_compute_indicators_v2(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/admin/compute-indicators-v2",
            json={"symbol": "BTC", "pos_usd": 150.0},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] == 1
    assert data["errors"] == 0
    assert data["results"][0]["status"] == "ok"


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


# ---------------------------------------------------------------------------
# Smart OHLCV update endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_smart_update_ohlcv_unknown_instrument(app):
    """POST /v1/admin/smart-update-ohlcv with an unknown instrument_id returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/admin/smart-update-ohlcv",
            json={"instrument_id": "nonexistent-instrument-xyz"},
        )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_smart_update_ohlcv_with_mocked_binance(patched_db, app):
    """POST /v1/admin/smart-update-ohlcv with mocked Binance returns correct step list
    and total_written."""
    from datetime import datetime, timedelta, timezone
    from unittest.mock import AsyncMock, patch

    from market_data.models.ohlcv import OHLCVRecord

    # Seed a Binance data source and mark BTC as having 1m coverage
    patched_db.execute(
        "INSERT INTO data_source (data_source_id, name, short_name, base_url)"
        " VALUES (99, 'Binance', 'binance', 'https://binance.com')"
        " ON CONFLICT (data_source_id) DO NOTHING",
    )
    patched_db.execute(
        "INSERT INTO ohlcv_data_available"
        " (instrument_id, data_source_id, has_1m, has_5m, has_1h, has_1d)"
        " VALUES ('uuid-btc-001', 99, TRUE, FALSE, FALSE, FALSE)"
        " ON CONFLICT (instrument_id, data_source_id) DO NOTHING",
    )

    # Build 3 fake 1m records (all in the same hour bucket → 1 synthetic 1h candle)
    now = datetime.now(tz=timezone.utc)
    hour_ts = now.replace(minute=0, second=0, microsecond=0)
    records_1m = [
        OHLCVRecord(
            instrument_id="uuid-btc-001",
            interval="1m",
            ts=hour_ts + timedelta(minutes=i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.5 + i,
            volume=1.0,
            source="binance",
        )
        for i in range(3)
    ]

    with (
        patch(
            "market_data.ingestion.jobs._run_interval_job",
            new=AsyncMock(return_value={"written": 5}),
        ),
        patch(
            "market_data.connectors.binance.BinanceConnector.fetch_ohlcv",
            new=AsyncMock(return_value=records_1m),
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/v1/admin/smart-update-ohlcv",
                json={"instrument_id": "uuid-btc-001"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert "steps" in data
    assert "total_written" in data

    steps_by_name = {s["step"]: s for s in data["steps"]}

    # 1h freshness check: data is from 2023 → stale
    assert "1h_freshness_check" in steps_by_name
    assert steps_by_name["1h_freshness_check"]["status"] == "stale"
    assert steps_by_name["1h_freshness_check"]["threshold_hours"] == 5

    # 1h ingest ran because data was stale
    assert steps_by_name["1h_ingest"]["status"] == "ok"
    assert steps_by_name["1h_ingest"]["written"] == 5

    # Binance was available
    assert steps_by_name["binance_availability"]["status"] == "available"

    # 1m fetch succeeded
    assert steps_by_name["1m_fetch"]["status"] == "ok"
    assert steps_by_name["1m_fetch"]["fetched"] == 3

    # Aggregation produced 1 synthetic 1h candle (all 3 records in same hour)
    assert steps_by_name["1h_aggregation"]["status"] == "ok"
    assert steps_by_name["1h_aggregation"]["written"] == 1

    # total_written = 5 (ingest) + 1 (aggregated 1h candle)
    assert data["total_written"] == 6


@pytest.mark.asyncio
async def test_console_no_best_sma_controls(app):
    """GET /console must not contain the removed Best SMA action-bar controls."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/console")
    assert resp.status_code == 200
    html = resp.text
    assert "INP_BEST_SMA_POS_USD" not in html
    assert "BTN_COMPUTE_BEST_SMA_V2" not in html


@pytest.mark.asyncio
async def test_console_no_best_sma_section(app):
    """GET /console must not contain the removed Best SMA Exit V1 section."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/console")
    assert resp.status_code == 200
    assert "best-sma-v2-section" not in resp.text
