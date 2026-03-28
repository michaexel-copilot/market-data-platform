"""CoinMarketCap connector — crypto OHLCV + instrument list + fundamentals."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

from market_data.connectors.base import to_float, to_utc, with_backoff
from market_data.connectors.rate_limiter import RateLimiter
from market_data.models.enums import AssetClass, Interval
from market_data.models.fundamentals import FundamentalsRecord
from market_data.models.instrument import InstrumentCryptoRecord, InstrumentRecord
from market_data.models.ohlcv import OHLCVRecord

_BASE_URL = "https://pro-api.coinmarketcap.com/v2"
_RATE = float(os.getenv("CMC_RATE", "5"))

_INTERVAL_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "1h": "1h",
    "1d": "daily",
}


class CoinMarketCapConnector:
    name = "coinmarketcap"
    supported_asset_classes = [AssetClass.CRYPTO]
    supported_intervals: list = []  # OHLCV historical requires a paid CMC plan

    def __init__(self) -> None:
        self._api_key = os.getenv("CMC_API_KEY", "")
        self._rl = RateLimiter(rate=_RATE, burst=_RATE)

    def _headers(self) -> dict[str, str]:
        return {"X-CMC_PRO_API_KEY": self._api_key, "Accept": "application/json"}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        await self._rl.acquire()
        async with httpx.AsyncClient(headers=self._headers(), timeout=30) as client:
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
        if not self._api_key:
            return []
        cmc_interval = _INTERVAL_MAP.get(str(interval), "daily")
        try:
            data = await self._get(
                "/cryptocurrency/ohlcv/historical",
                params={
                    "slug": instrument_id,
                    "time_start": to_utc(since).isoformat(),
                    "time_end": to_utc(until).isoformat(),
                    "interval": cmc_interval,
                    "convert": "USD",
                },
            )
        except httpx.HTTPStatusError:
            return []
        quotes = (
            data.get("data", {}).get("quotes")
            or data.get("data", [{}])[0].get("quotes", [])
            if isinstance(data.get("data"), dict)
            else []
        )
        records: list[OHLCVRecord] = []
        for q in quotes:
            ohlcv = q.get("quote", {}).get("USD", {})
            ts_str = q.get("time_open") or q.get("timestamp")
            if not ts_str:
                continue
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            records.append(
                OHLCVRecord(
                    instrument_id=instrument_id,
                    interval=interval,
                    ts=ts,
                    open=float(ohlcv.get("open", 0)),
                    high=float(ohlcv.get("high", 0)),
                    low=float(ohlcv.get("low", 0)),
                    close=float(ohlcv.get("close", 0)),
                    volume=to_float(ohlcv.get("volume")),
                    market_cap=to_float(ohlcv.get("market_cap")),
                    source=self.name,
                )
            )
        return records

    @with_backoff()
    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        if asset_class != AssetClass.CRYPTO or not self._api_key:
            return []
        try:
            data = await self._get(
                "/cryptocurrency/map",
                params={"listing_status": "active", "limit": 5000},
            )
        except httpx.HTTPStatusError:
            return []
        records: list[InstrumentRecord] = []
        for item in data.get("data", []):
            try:
                records.append(
                    InstrumentRecord(
                        instrument_id=str(item["slug"]),
                        ticker=(item.get("symbol") or "").upper(),
                        full_name=item.get("name"),
                        asset_class=AssetClass.CRYPTO,
                        is_active=item.get("is_active", 1) == 1,
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
            data = await self._get(
                "/cryptocurrency/info",
                params={"slug": instrument_id},
            )
        except httpx.HTTPStatusError:
            return None
        items = list(data.get("data", {}).values())
        if not items:
            return None
        item = items[0]
        return FundamentalsRecord(
            instrument_id=instrument_id,
            asset_class=AssetClass.CRYPTO,
            crypto=InstrumentCryptoRecord(
                instrument_id=instrument_id,
                total_supply=to_float(item.get("total_supply")),
                max_supply=to_float(item.get("max_supply")),
                circulating_supply=to_float(item.get("circulating_supply")),
                whitepaper_url=(item.get("urls") or {}).get("technical_doc", [None])[0],
                github_url=(item.get("urls") or {}).get("source_code", [None])[0],
            ),
        )


connector = CoinMarketCapConnector()
