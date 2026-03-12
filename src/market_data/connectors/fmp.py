"""Financial Modeling Prep (FMP) connector — equities + ETF OHLCV + fundamentals."""
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

_BASE_URL = "https://financialmodelingprep.com/api/v3"
_RATE = float(os.getenv("FMP_RATE", "5"))

_INTERVAL_MAP: dict[str, str] = {
    "1m": "1min",
    "5m": "5min",
    "1h": "1hour",
    "1d": "daily",
}


class FMPConnector:
    name = "fmp"
    supported_asset_classes = [
        AssetClass.EQUITY,
        AssetClass.ETF,
        AssetClass.CRYPTO,
        AssetClass.COMMODITY,
        AssetClass.FX,
        AssetClass.INDEX,
    ]
    supported_intervals = [
        Interval.ONE_MIN,
        Interval.FIVE_MIN,
        Interval.ONE_HOUR,
        Interval.ONE_DAY,
    ]

    def __init__(self) -> None:
        self._api_key = os.getenv("FMP_API_KEY", "")
        self._rl = RateLimiter(rate=_RATE, burst=_RATE)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        await self._rl.acquire()
        p = {"apikey": self._api_key, **(params or {})}
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
        iv = str(interval)
        fmp_interval = _INTERVAL_MAP.get(iv, "daily")
        from_str = to_utc(since).strftime("%Y-%m-%d")
        to_str = to_utc(until).strftime("%Y-%m-%d")
        if fmp_interval == "daily":
            path = f"/historical-price-full/{instrument_id.upper()}"
            try:
                data = await self._get(path, params={"from": from_str, "to": to_str})
            except httpx.HTTPStatusError:
                return []
            rows = data.get("historical", []) if isinstance(data, dict) else []
        else:
            path = f"/historical-chart/{fmp_interval}/{instrument_id.upper()}"
            try:
                data = await self._get(path, params={"from": from_str, "to": to_str})
            except httpx.HTTPStatusError:
                return []
            rows = data if isinstance(data, list) else []

        records: list[OHLCVRecord] = []
        for row in rows:
            ts_str = row.get("date") or row.get("datetime") or row.get("timestamp")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                records.append(
                    OHLCVRecord(
                        instrument_id=instrument_id,
                        interval=interval,
                        ts=ts,
                        open=float(row.get("open", 0) or 0),
                        high=float(row.get("high", 0) or 0),
                        low=float(row.get("low", 0) or 0),
                        close=float(row.get("close") or row.get("adjClose", 0) or 0),
                        volume=to_float(row.get("volume")),
                        vwap=to_float(row.get("vwap")),
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
        endpoint_map = {
            AssetClass.EQUITY: "/stock/list",
            AssetClass.ETF: "/etf/list",
            AssetClass.CRYPTO: "/symbol/available-cryptocurrencies",
        }
        path = endpoint_map.get(asset_class)
        if not path:
            return []
        try:
            data = await self._get(path)
        except httpx.HTTPStatusError:
            return []
        if not isinstance(data, list):
            return []
        records: list[InstrumentRecord] = []
        for item in data:
            try:
                records.append(
                    InstrumentRecord(
                        instrument_id=item.get("symbol", "").upper(),
                        ticker=item.get("symbol", "").upper(),
                        full_name=item.get("name"),
                        asset_class=asset_class,
                        exchange=item.get("exchangeShortName") or item.get("exchange"),
                    )
                )
            except Exception:
                continue
        return records

    @with_backoff()
    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        if not self._api_key:
            return None
        try:
            data = await self._get(f"/profile/{instrument_id.upper()}")
        except httpx.HTTPStatusError:
            return None
        items = data if isinstance(data, list) else []
        if not items:
            return None
        item = items[0]
        return FundamentalsRecord(
            instrument_id=instrument_id,
            asset_class=AssetClass.EQUITY,
            equity=InstrumentEquityRecord(
                instrument_id=instrument_id,
                isin=item.get("isin"),
                country_of_incorporation=item.get("country"),
                shares_outstanding=_safe_int(item.get("sharesOutstanding")),
            ),
        )


def _safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


connector = FMPConnector()
