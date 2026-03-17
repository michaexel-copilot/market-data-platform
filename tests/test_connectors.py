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


class TestHyperliquidConnector:
    """Unit tests for the Hyperliquid connector."""

    def test_k_prefix_stripped(self):
        from market_data.connectors.hyperliquid import _strip_k_prefix
        assert _strip_k_prefix("KPEPE") == "PEPE"
        assert _strip_k_prefix("KDOGE") == "DOGE"

    def test_k_prefix_not_stripped_for_short_symbol(self):
        from market_data.connectors.hyperliquid import _strip_k_prefix
        # "K" alone should not be stripped
        assert _strip_k_prefix("K") == "K"

    def test_no_k_prefix_unchanged(self):
        from market_data.connectors.hyperliquid import _strip_k_prefix
        assert _strip_k_prefix("BTC") == "BTC"
        assert _strip_k_prefix("ETH") == "ETH"

    def test_fetch_hl_pairs_parses_response(self):
        from market_data.connectors.hyperliquid import HyperliquidConnector
        connector = HyperliquidConnector()
        fake_response = {
            "universe": [
                {"name": "BTC", "szDecimals": 5, "maxLeverage": 50},
                {"name": "KPEPE", "szDecimals": 0, "maxLeverage": 3},
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            pairs = asyncio.run(connector.fetch_hl_pairs("mainnet"))

        assert len(pairs) == 2
        btc = next(p for p in pairs if p.base_ticker == "BTC")
        assert btc.hl_symbol == "BTC/USDC:USDC"
        assert btc.max_leverage == 50

        kpepe = next(p for p in pairs if p.base_ticker == "PEPE")
        assert kpepe.hl_symbol == "KPEPE/USDC:USDC"
        assert kpepe.base_ticker == "PEPE"

    def test_fetch_ohlcv_raises_not_implemented(self):
        from market_data.connectors.hyperliquid import HyperliquidConnector
        from market_data.models.enums import Interval
        from datetime import datetime, timezone
        connector = HyperliquidConnector()
        with pytest.raises(NotImplementedError):
            asyncio.run(connector.fetch_ohlcv(
                "btc", Interval.ONE_DAY,
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 2, tzinfo=timezone.utc),
            ))

    def test_reconcile_matched_and_unmatched(self):
        from market_data.connectors.hyperliquid import reconcile_hl_pairs
        from market_data.models.instrument import HLPairRecord

        pairs = [
            HLPairRecord(hl_symbol="BTC/USDC:USDC", base_ticker="BTC", lot_size=1e-5, tick_size=0.0, max_leverage=50),
            HLPairRecord(hl_symbol="UNKNOWN/USDC:USDC", base_ticker="UNKNOWN", lot_size=1.0, tick_size=0.0, max_leverage=3),
        ]

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [("uuid-btc-001", "BTC")]

        result = reconcile_hl_pairs(pairs, mock_conn)
        assert len(result) == 1
        assert result[0][0] == "uuid-btc-001"
        assert result[0][1].base_ticker == "BTC"

    def test_reconcile_case_insensitive(self):
        from market_data.connectors.hyperliquid import reconcile_hl_pairs
        from market_data.models.instrument import HLPairRecord

        pairs = [
            HLPairRecord(hl_symbol="ADA/USDC:USDC", base_ticker="ada", lot_size=1.0, tick_size=0.0, max_leverage=10),
        ]
        mock_conn = MagicMock()
        # DB returns upper-cased ticker
        mock_conn.execute.return_value.fetchall.return_value = [("uuid-ada-001", "ADA")]

        result = reconcile_hl_pairs(pairs, mock_conn)
        assert len(result) == 1
        assert result[0][0] == "uuid-ada-001"
