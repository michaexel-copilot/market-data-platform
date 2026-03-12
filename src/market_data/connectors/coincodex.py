"""CoinCodex connector — crypto OHLCV + instrument list."""
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

_BASE_URL = "https://coincodex.com/api/coincodex"
_RATE = float(os.getenv("COINCODEX_RATE", "5"))

# CoinCodex OHLCV interval labels
_INTERVAL_MAP: dict[str, str] = {
    "1d": "1d",
    "1h": "1h",
    "5m": "5m",
    "1m": "1m",
}


class CoinCodexConnector:
    name = "coincodex"
    supported_asset_classes = [AssetClass.CRYPTO]
    supported_intervals = [
        Interval.ONE_DAY,
        Interval.ONE_HOUR,
        Interval.FIVE_MIN,
        Interval.ONE_MIN,
    ]

    def __init__(self) -> None:
        self._rl = RateLimiter(rate=_RATE, burst=_RATE)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        await self._rl.acquire()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{_BASE_URL}{path}", params=params)
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
        since_ts = int(to_utc(since).timestamp())
        until_ts = int(to_utc(until).timestamp())
        granularity = _INTERVAL_MAP.get(str(interval), "1d")
        try:
            data = await self._get(
                f"/get_coin_history/{instrument_id}/{since_ts}/{until_ts}/{granularity}"
            )
        except httpx.HTTPStatusError:
            return []
        records: list[OHLCVRecord] = []
        if isinstance(data, list):
            for row in data:
                # row: [timestamp, open, high, low, close, volume]
                if len(row) < 5:
                    continue
                ts = datetime.fromtimestamp(row[0], tz=timezone.utc)
                records.append(
                    OHLCVRecord(
                        instrument_id=instrument_id,
                        interval=interval,
                        ts=ts,
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=to_float(row[5]) if len(row) > 5 else None,
                        source=self.name,
                    )
                )
        return records

    @with_backoff()
    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        if asset_class != AssetClass.CRYPTO:
            return []
        try:
            data = await self._get("/get_coin_list")
        except httpx.HTTPStatusError:
            return []
        records: list[InstrumentRecord] = []
        if isinstance(data, list):
            for item in data:
                try:
                    records.append(
                        InstrumentRecord(
                            instrument_id=item.get("id") or item.get("symbol", "").lower(),
                            ticker=(item.get("symbol") or "").upper(),
                            full_name=item.get("name"),
                            asset_class=AssetClass.CRYPTO,
                        )
                    )
                except Exception:
                    continue
        return records

    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        # CoinCodex does not provide rich fundamentals; not implemented
        return None


connector = CoinCodexConnector()
