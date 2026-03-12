"""Binance connector — crypto OHLCV via public klines endpoint (no API key required)."""
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

_BASE_URL = "https://api.binance.com/api/v3"
_RATE = float(os.getenv("BINANCE_RATE", "10"))

_INTERVAL_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "1h": "1h",
    "1d": "1d",
}


class BinanceConnector:
    name = "binance"
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
        # instrument_id should be Binance symbol e.g. BTCUSDT
        kline_interval = _INTERVAL_MAP.get(str(interval), "1d")
        since_ms = int(to_utc(since).timestamp() * 1000)
        until_ms = int(to_utc(until).timestamp() * 1000)
        symbol = instrument_id.upper().replace("-", "").replace("/", "")

        records: list[OHLCVRecord] = []
        start_ms = since_ms
        while start_ms < until_ms:
            try:
                data = await self._get(
                    "/klines",
                    params={
                        "symbol": symbol,
                        "interval": kline_interval,
                        "startTime": start_ms,
                        "endTime": until_ms,
                        "limit": 1000,
                    },
                )
            except httpx.HTTPStatusError:
                break
            if not data:
                break
            for row in data:
                # [open_time, open, high, low, close, volume, close_time, ...]
                ts = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc)
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
                            volume=to_float(row[5]),
                            trade_count=row[8] if len(row) > 8 else None,
                            source=self.name,
                        )
                    )
                except Exception:
                    continue
            last_open_time = data[-1][0]
            if last_open_time >= until_ms or len(data) < 1000:
                break
            start_ms = last_open_time + 1
        return records

    @with_backoff()
    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        if asset_class != AssetClass.CRYPTO:
            return []
        try:
            data = await self._get("/exchangeInfo")
        except httpx.HTTPStatusError:
            return []
        records: list[InstrumentRecord] = []
        for sym in data.get("symbols", []):
            if sym.get("status") != "TRADING":
                continue
            try:
                records.append(
                    InstrumentRecord(
                        instrument_id=sym["symbol"],
                        ticker=sym["baseAsset"].upper(),
                        full_name=sym["symbol"],
                        asset_class=AssetClass.CRYPTO,
                        quote_currency=sym.get("quoteAsset"),
                    )
                )
            except Exception:
                continue
        return records

    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        return None


connector = BinanceConnector()
