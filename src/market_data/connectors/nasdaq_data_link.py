"""Nasdaq Data Link (formerly Quandl) connector — equities + commodities + macro data."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

from market_data.connectors.base import to_float, to_utc, with_backoff
from market_data.connectors.rate_limiter import RateLimiter
from market_data.models.enums import AssetClass, Interval
from market_data.models.fundamentals import FundamentalsRecord
from market_data.models.instrument import InstrumentRecord
from market_data.models.ohlcv import OHLCVRecord

_BASE_URL = "https://data.nasdaq.com/api/v3"
_RATE = float(os.getenv("NASDAQ_DATA_LINK_RATE", "5"))


class NasdaqDataLinkConnector:
    name = "nasdaq_data_link"
    supported_asset_classes = [
        AssetClass.EQUITY,
        AssetClass.COMMODITY,
        AssetClass.INDEX,
        AssetClass.FUTURE,
    ]
    supported_intervals = [Interval.ONE_DAY]

    def __init__(self) -> None:
        self._api_key = os.getenv("NASDAQ_DATA_LINK_KEY", "")
        self._rl = RateLimiter(rate=_RATE, burst=_RATE)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        await self._rl.acquire()
        p = {"api_key": self._api_key, **(params or {})}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{_BASE_URL}{path}", params=p)
            resp.raise_for_status()
            return resp.json()

    @with_backoff()
    async def fetch_ohlcv(
        self,
        instrument_id: str,
        interval: Interval,
        since: datetime,
        until: datetime,
    ) -> list[OHLCVRecord]:
        """instrument_id format: DATABASE/DATASET  e.g. WIKI/AAPL or CHRIS/CME_ES1"""
        if interval != Interval.ONE_DAY:
            return []
        if not self._api_key:
            return []
        from_str = to_utc(since).strftime("%Y-%m-%d")
        to_str = to_utc(until).strftime("%Y-%m-%d")
        path = f"/datasets/{instrument_id}/data.json"
        try:
            data = await self._get(path, params={"start_date": from_str, "end_date": to_str, "order": "asc"})
        except httpx.HTTPStatusError:
            return []

        dataset_data = data.get("dataset_data", {})
        column_names: list[str] = [c.lower() for c in dataset_data.get("column_names", [])]
        rows: list[list[Any]] = dataset_data.get("data", [])

        def _col(row: list[Any], name: str, fallback: Any = None) -> Any:
            if name in column_names:
                return row[column_names.index(name)]
            return fallback

        records: list[OHLCVRecord] = []
        for row in rows:
            ts_str = _col(row, "date")
            if not ts_str:
                continue
            ts = datetime.fromisoformat(str(ts_str))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            try:
                records.append(
                    OHLCVRecord(
                        instrument_id=instrument_id,
                        interval=Interval.ONE_DAY,
                        ts=ts,
                        open=float(_col(row, "open", 0) or 0),
                        high=float(_col(row, "high", 0) or 0),
                        low=float(_col(row, "low", 0) or 0),
                        close=float(_col(row, "close") or _col(row, "adj. close", 0) or 0),
                        volume=to_float(_col(row, "volume") or _col(row, "adj. volume")),
                        source=self.name,
                    )
                )
            except Exception:
                continue
        return records

    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        return []

    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        return None


connector = NasdaqDataLinkConnector()
