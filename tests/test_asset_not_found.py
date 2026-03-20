"""Tests for asset-not-found suppression in the ingestion job layer."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def _make_404_error(url: str = "https://example.com/api/asset?interval=5m") -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    response = httpx.Response(404, request=request)
    return httpx.HTTPStatusError("404 Not Found", request=request, response=response)


class TestAssetNotFoundJobIntegration:
    """Integration tests for 404 recording and pre-fetch suppression in jobs."""

    def test_404_is_recorded_and_logged(self, db_conn):
        """A connector 404 triggers record_not_found and logs INFO."""
        from market_data.db.asset_not_found import load_blocked
        from market_data.ingestion import jobs
        from market_data.models.enums import Interval

        fake_connector = MagicMock()
        fake_connector.name = "test-source"
        fake_connector.fetch_ohlcv = AsyncMock(side_effect=_make_404_error())

        with (
            patch.object(jobs, "_active_instrument_ids", return_value=["bitcoin"]),
            patch.object(jobs.registry, "by_interval", return_value=[fake_connector]),
            patch.object(jobs, "get_connection", return_value=db_conn),
        ):
            asyncio.run(jobs._run_interval_job(Interval.FIVE_MIN))

        blocked = load_blocked(db_conn, "5m")
        assert ("bitcoin", "test-source") in blocked

    def test_blocked_combination_is_skipped(self, db_conn):
        """An instrument already in asset_not_found is not fetched."""
        from market_data.db.asset_not_found import record_not_found
        from market_data.ingestion import jobs
        from market_data.models.enums import Interval

        # Pre-populate the suppression table
        record_not_found(db_conn, "bitcoin", "test-source", "5m", "https://example.com/")

        fake_connector = MagicMock()
        fake_connector.name = "test-source"
        fake_connector.fetch_ohlcv = AsyncMock()

        with (
            patch.object(jobs, "_active_instrument_ids", return_value=["bitcoin"]),
            patch.object(jobs.registry, "by_interval", return_value=[fake_connector]),
            patch.object(jobs, "get_connection", return_value=db_conn),
        ):
            asyncio.run(jobs._run_interval_job(Interval.FIVE_MIN))

        fake_connector.fetch_ohlcv.assert_not_called()

    def test_404_does_not_disable_connector(self, db_conn):
        """A 404 does not call registry.disable and does not break the loop."""
        from market_data.ingestion import jobs
        from market_data.models.enums import Interval

        fake_connector = MagicMock()
        fake_connector.name = "test-source"
        # First instrument → 404, second instrument → success
        fake_connector.fetch_ohlcv = AsyncMock(
            side_effect=[_make_404_error(), []]
        )

        with (
            patch.object(jobs, "_active_instrument_ids", return_value=["bitcoin", "ethereum"]),
            patch.object(jobs.registry, "by_interval", return_value=[fake_connector]),
            patch.object(jobs, "get_connection", return_value=db_conn),
            patch.object(jobs.registry, "disable") as mock_disable,
        ):
            asyncio.run(jobs._run_interval_job(Interval.FIVE_MIN))

        mock_disable.assert_not_called()
        assert fake_connector.fetch_ohlcv.call_count == 2
