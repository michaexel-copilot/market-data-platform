"""Tiingo connector — equities + crypto OHLCV + fundamentals."""
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

_BASE_URL = "https://api.tiingo.com"
_RATE = float(os.getenv("TIINGO_RATE", "5"))

_RESAMPLE_MAP: dict[str, str] = {
    "1m": "1min",
    "5m": "5min",
    "1h": "1hour",
    "1d": "1day",
}


class TiingoConnector:
    name = "tiingo"
    supported_asset_classes = [
        AssetClass.EQUITY,
        AssetClass.ETF,
        AssetClass.CRYPTO,
    ]
    supported_intervals = [
        Interval.ONE_MIN,
        Interval.FIVE_MIN,
        Interval.ONE_HOUR,
        Interval.ONE_DAY,
    ]

    def __init__(self) -> None:
        self._api_key = os.getenv("TIINGO_API_KEY", "")
        self._rl = RateLimiter(rate=_RATE, burst=_RATE)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Token {self._api_key}", "Content-Type": "application/json"}

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
        resample = _RESAMPLE_MAP.get(str(interval), "1day")
        since_str = to_utc(since).isoformat()
        until_str = to_utc(until).isoformat()
        is_crypto = "/" in instrument_id  # e.g. btcusd treated as crypto

        if is_crypto or interval == Interval.ONE_DAY:
            path = f"/tiingo/crypto/prices" if is_crypto else f"/tiingo/daily/{instrument_id}/prices"
            params: dict[str, Any] = {
                "startDate": since_str,
                "endDate": until_str,
                "resampleFreq": resample,
            }
            if is_crypto:
                params["tickers"] = instrument_id
        else:
            path = f"/iex/{instrument_id}"
            params = {
                "startDate": since_str,
                "endDate": until_str,
                "resampleFreq": resample,
            }
        try:
            data = await self._get(path, params=params)
        except httpx.HTTPStatusError:
            return []

        rows = data if isinstance(data, list) else (data[0].get("priceData", []) if data else [])
        records: list[OHLCVRecord] = []
        for row in rows:
            ts_str = row.get("date") or row.get("dateTime")
            if not ts_str:
                continue
            ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            try:
                records.append(
                    OHLCVRecord(
                        instrument_id=instrument_id,
                        interval=interval,
                        ts=ts,
                        open=float(row.get("open", 0) or 0),
                        high=float(row.get("high", 0) or 0),
                        low=float(row.get("low", 0) or 0),
                        close=float(row.get("close") or row.get("adjClose", 0) or 0),
                        volume=to_float(row.get("volume") or row.get("volumeNotional")),
                        source=self.name,
                    )
                )
            except Exception:
                continue
        return records

    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        return []

    @with_backoff()
    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        if not self._api_key:
            return None
        try:
            data = await self._get(f"/tiingo/daily/{instrument_id}")
        except httpx.HTTPStatusError:
            return None
        if not data or not isinstance(data, dict):
            return None
        return FundamentalsRecord(
            instrument_id=instrument_id,
            asset_class=AssetClass.EQUITY,
            equity=InstrumentEquityRecord(
                instrument_id=instrument_id,
            ),
        )


connector = TiingoConnector()
