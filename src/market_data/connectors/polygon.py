"""Polygon.io connector — US equities + crypto OHLCV + instruments."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

from market_data.connectors.base import to_float, to_utc, with_backoff
from market_data.connectors.rate_limiter import RateLimiter
from market_data.models.enums import AssetClass, Interval
from market_data.models.fundamentals import FundamentalsRecord
from market_data.models.instrument import InstrumentEquityRecord, InstrumentRecord
from market_data.models.ohlcv import OHLCVRecord

_BASE_URL = "https://api.polygon.io"
_RATE = float(os.getenv("POLYGON_RATE", "5"))

_TIMESPAN_MAP: dict[str, tuple[str, int]] = {
    "1m": ("minute", 1),
    "5m": ("minute", 5),
    "1h": ("hour", 1),
    "1d": ("day", 1),
}


class PolygonConnector:
    name = "polygon"
    supported_asset_classes = [
        AssetClass.EQUITY,
        AssetClass.ETF,
        AssetClass.CRYPTO,
        AssetClass.FX,
        AssetClass.INDEX,
        AssetClass.FUTURE,
    ]
    supported_intervals = [
        Interval.ONE_MIN,
        Interval.FIVE_MIN,
        Interval.ONE_HOUR,
        Interval.ONE_DAY,
    ]

    def __init__(self) -> None:
        self._api_key = os.getenv("POLYGON_API_KEY", "")
        self._rl = RateLimiter(rate=_RATE, burst=_RATE)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        await self._rl.acquire()
        p = {"apiKey": self._api_key, **(params or {})}
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
        if not self._api_key:
            return []
        timespan, multiplier = _TIMESPAN_MAP.get(str(interval), ("day", 1))
        from_str = to_utc(since).strftime("%Y-%m-%d")
        to_str = to_utc(until).strftime("%Y-%m-%d")
        # Polygon uses X: prefix for crypto, C: for FX
        ticker = instrument_id.upper()
        try:
            data = await self._get(
                f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_str}/{to_str}",
                params={"adjusted": "true", "sort": "asc", "limit": 50000},
            )
        except httpx.HTTPStatusError:
            return []
        records: list[OHLCVRecord] = []
        for bar in data.get("results", []):
            ts = datetime.fromtimestamp(bar["t"] / 1000, tz=timezone.utc)
            try:
                records.append(
                    OHLCVRecord(
                        instrument_id=instrument_id,
                        interval=interval,
                        ts=ts,
                        open=float(bar["o"]),
                        high=float(bar["h"]),
                        low=float(bar["l"]),
                        close=float(bar["c"]),
                        volume=to_float(bar.get("v")),
                        vwap=to_float(bar.get("vw")),
                        trade_count=bar.get("n"),
                        source=self.name,
                    )
                )
            except Exception:
                continue
        return records

    @with_backoff()
    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        if not self._api_key:
            return []
        type_map = {
            AssetClass.EQUITY: "CS",
            AssetClass.ETF: "ETF",
            AssetClass.CRYPTO: "crypto",
        }
        market_type = type_map.get(asset_class)
        if not market_type:
            return []
        params: dict[str, Any] = {"active": "true", "limit": 1000}
        if asset_class == AssetClass.CRYPTO:
            params["market"] = "crypto"
        else:
            params["type"] = market_type

        records: list[InstrumentRecord] = []
        cursor_url: str | None = f"{_BASE_URL}/v3/reference/tickers"
        while cursor_url:
            try:
                await self._rl.acquire()
                p = {"apiKey": self._api_key, **params}
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(cursor_url, params=p)
                    resp.raise_for_status()
                    data = resp.json()
            except httpx.HTTPStatusError:
                break
            for item in data.get("results", []):
                try:
                    records.append(
                        InstrumentRecord(
                            instrument_id=item.get("ticker", ""),
                            ticker=item.get("ticker", "").upper(),
                            full_name=item.get("name"),
                            asset_class=asset_class,
                            exchange=item.get("primary_exchange"),
                        )
                    )
                except Exception:
                    continue
            next_url = data.get("next_url")
            cursor_url = f"{next_url}&apiKey={self._api_key}" if next_url else None
            # Clear params so the next_url carries them
            params = {}
        return records

    @with_backoff()
    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        if not self._api_key:
            return None
        try:
            data = await self._get(f"/v3/reference/tickers/{instrument_id.upper()}")
        except httpx.HTTPStatusError:
            return None
        item = data.get("results", {})
        return FundamentalsRecord(
            instrument_id=instrument_id,
            asset_class=AssetClass.EQUITY,
            equity=InstrumentEquityRecord(
                instrument_id=instrument_id,
                composite_figi=item.get("composite_figi"),
                figi=item.get("share_class_figi"),
            ),
        )


connector = PolygonConnector()
