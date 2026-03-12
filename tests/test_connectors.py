"""Tests for connector field mapping and timestamp normalisation."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from market_data.models.enums import AssetClass, Interval


class TestCoinGeckoConnector:
    def test_records_have_utc_timestamps(self):
        from market_data.connectors.coingecko import CoinGeckoConnector
        connector = CoinGeckoConnector()
        # Simulate market_chart/range response
        fake_data = {
            "prices": [
                [1_700_000_000_000, 35000.0],
                [1_700_086_400_000, 35500.0],
            ],
            "total_volumes": [],
            "market_caps": [],
        }
        with patch.object(connector, "_get", new_callable=AsyncMock, return_value=fake_data):
            records = asyncio.run(
                connector.fetch_ohlcv(
                    "bitcoin",
                    Interval.ONE_DAY,
                    datetime(2023, 11, 14, tzinfo=timezone.utc),
                    datetime(2023, 11, 16, tzinfo=timezone.utc),
                )
            )
        assert len(records) == 2
        for r in records:
            assert r.ts.tzinfo is not None
            assert r.instrument_id == "bitcoin"
            assert r.source == "coingecko"

    def test_instrument_list_maps_fields(self):
        from market_data.connectors.coingecko import CoinGeckoConnector
        connector = CoinGeckoConnector()
        fake_list = [
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
            {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
        ]
        with patch.object(connector, "_get", new_callable=AsyncMock, return_value=fake_list):
            instruments = asyncio.run(connector.fetch_instruments(AssetClass.CRYPTO))
        assert len(instruments) == 2
        btc = next(i for i in instruments if i.instrument_id == "bitcoin")
        assert btc.ticker == "BTC"
        assert btc.full_name == "Bitcoin"
        assert btc.asset_class == AssetClass.CRYPTO


class TestBinanceConnector:
    def test_klines_parsed_correctly(self):
        from market_data.connectors.binance import BinanceConnector
        connector = BinanceConnector()
        # Binance klines: [open_time, open, high, low, close, volume, close_time, ...]
        fake_klines = [
            [1_700_000_000_000, "35000.0", "35100.0", "34900.0", "35050.0", "100.5", 1_700_003_599_999, "", 0, "", "", ""],
        ]
        with patch.object(connector, "_get", new_callable=AsyncMock, return_value=fake_klines):
            records = asyncio.run(
                connector.fetch_ohlcv(
                    "BTCUSDT",
                    Interval.ONE_DAY,
                    datetime(2023, 11, 14, tzinfo=timezone.utc),
                    datetime(2023, 11, 15, tzinfo=timezone.utc),
                )
            )
        assert len(records) == 1
        r = records[0]
        assert r.open == 35000.0
        assert r.close == 35050.0
        assert r.volume == pytest.approx(100.5)
        assert r.ts.tzinfo is not None


class TestKrakenConnector:
    def test_ohlc_response_parsed(self):
        from market_data.connectors.kraken import KrakenConnector
        connector = KrakenConnector()
        fake_data = {
            "error": [],
            "result": {
                "XXBTZUSD": [
                    [1700000000, "35000.0", "35100.0", "34800.0", "35050.0", "35000.0", "50.0", 200],
                ],
                "last": 1700000000,
            },
        }
        with patch.object(connector, "_get", new_callable=AsyncMock, return_value=fake_data):
            records = asyncio.run(
                connector.fetch_ohlcv(
                    "XBTUSDT",
                    Interval.ONE_DAY,
                    datetime(2023, 11, 14, tzinfo=timezone.utc),
                    datetime(2023, 11, 16, tzinfo=timezone.utc),
                )
            )
        assert len(records) == 1
        r = records[0]
        assert r.open == 35000.0
        assert r.trade_count == 200
