"""Kraken connector — crypto OHLCV + instrument list (public API, no key required)."""
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

_BASE_URL = "https://api.kraken.com/0/public"
_RATE = float(os.getenv("KRAKEN_RATE", "5"))

# Kraken OHLC interval in minutes
_INTERVAL_MINUTES: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "1h": 60,
    "1d": 1440,
}


class KrakenConnector:
    name = "kraken"
    supported_asset_classes = [AssetClass.CRYPTO]
    supported_intervals = [
        Interval.ONE_MIN,
        Interval.FIVE_MIN,
        Interval.ONE_HOUR,
        Interval.ONE_DAY,
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
        interval_min = _INTERVAL_MINUTES.get(str(interval), 1440)
        since_ts = int(to_utc(since).timestamp())
        until_ts = int(to_utc(until).timestamp())
        # Kraken pair names: normalise e.g. BTC/USDT → XBTUSDT or use as-is
        pair = instrument_id.upper().replace("/", "").replace("-", "")
        try:
            data = await self._get(
                "/OHLC",
                params={"pair": pair, "interval": interval_min, "since": since_ts},
            )
        except httpx.HTTPStatusError:
            return []
        errors = data.get("error", [])
        if errors:
            return []
        result = data.get("result", {})
        # result has one key = normalised pair name, plus 'last'
        ohlc_data: list[list[Any]] = []
        for key, val in result.items():
            if key != "last" and isinstance(val, list):
                ohlc_data = val
                break

        records: list[OHLCVRecord] = []
        for row in ohlc_data:
            # [time, open, high, low, close, vwap, volume, count]
            ts = datetime.fromtimestamp(float(row[0]), tz=timezone.utc)
            if ts.timestamp() > until_ts:
                break
            try:
                records.append(
                    OHLCVRecord(
                        instrument_id=instrument_id,
                        interval=interval,
                        ts=ts,
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        vwap=to_float(row[5]),
                        volume=to_float(row[6]),
                        trade_count=int(row[7]) if len(row) > 7 else None,
                        source=self.name,
                    )
                )
            except Exception:
                continue
        return records

    @with_backoff()
    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        if asset_class != AssetClass.CRYPTO:
            return []
        try:
            data = await self._get("/AssetPairs")
        except httpx.HTTPStatusError:
            return []
        records: list[InstrumentRecord] = []
        for symbol, info in data.get("result", {}).items():
            try:
                records.append(
                    InstrumentRecord(
                        instrument_id=symbol,
                        ticker=info.get("base", symbol).upper(),
                        full_name=info.get("wsname") or symbol,
                        asset_class=AssetClass.CRYPTO,
                        quote_currency=info.get("quote"),
                    )
                )
            except Exception:
                continue
        return records

    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        return None


connector = KrakenConnector()
