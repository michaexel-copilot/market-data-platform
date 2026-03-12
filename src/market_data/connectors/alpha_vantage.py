"""Alpha Vantage connector — equities + crypto + FX OHLCV + fundamentals."""
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

_BASE_URL = "https://www.alphavantage.co/query"
_RATE = float(os.getenv("ALPHA_VANTAGE_RATE", "2"))  # free tier: 5 req/min burst

_FUNCTION_MAP: dict[str, str] = {
    "1m": "TIME_SERIES_INTRADAY",
    "5m": "TIME_SERIES_INTRADAY",
    "1h": "TIME_SERIES_INTRADAY",
    "1d": "TIME_SERIES_DAILY_ADJUSTED",
}
_INTERVAL_PARAM: dict[str, str] = {
    "1m": "1min",
    "5m": "5min",
    "1h": "60min",
}
_TS_KEY_MAP: dict[str, str] = {
    "1m": "Time Series (1min)",
    "5m": "Time Series (5min)",
    "1h": "Time Series (60min)",
    "1d": "Time Series (Daily)",
}


class AlphaVantageConnector:
    name = "alpha_vantage"
    supported_asset_classes = [
        AssetClass.EQUITY,
        AssetClass.ETF,
        AssetClass.CRYPTO,
        AssetClass.FX,
    ]
    supported_intervals = [
        Interval.ONE_MIN,
        Interval.FIVE_MIN,
        Interval.ONE_HOUR,
        Interval.ONE_DAY,
    ]

    def __init__(self) -> None:
        self._api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
        self._rl = RateLimiter(rate=_RATE, burst=_RATE)

    async def _get(self, params: dict[str, Any]) -> Any:
        await self._rl.acquire()
        p = {"apikey": self._api_key, **params}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(_BASE_URL, params=p)
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
        iv = str(interval)
        fn = _FUNCTION_MAP.get(iv, "TIME_SERIES_DAILY_ADJUSTED")
        params: dict[str, Any] = {"function": fn, "symbol": instrument_id, "outputsize": "full"}
        if iv in _INTERVAL_PARAM:
            params["interval"] = _INTERVAL_PARAM[iv]
        try:
            data = await self._get(params)
        except httpx.HTTPStatusError:
            return []
        ts_key = _TS_KEY_MAP.get(iv)
        if not ts_key or ts_key not in data:
            return []
        since_utc = to_utc(since)
        until_utc = to_utc(until)
        records: list[OHLCVRecord] = []
        for dt_str, bar in data[ts_key].items():
            try:
                ts = datetime.fromisoformat(dt_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if not (since_utc <= ts <= until_utc):
                    continue
                records.append(
                    OHLCVRecord(
                        instrument_id=instrument_id,
                        interval=interval,
                        ts=ts,
                        open=float(bar.get("1. open") or bar.get("open", 0)),
                        high=float(bar.get("2. high") or bar.get("high", 0)),
                        low=float(bar.get("3. low") or bar.get("low", 0)),
                        close=float(
                            bar.get("5. adjusted close")
                            or bar.get("4. close")
                            or bar.get("close", 0)
                        ),
                        volume=to_float(bar.get("6. volume") or bar.get("5. volume") or bar.get("volume")),
                        source=self.name,
                    )
                )
            except Exception:
                continue
        return records

    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        # Alpha Vantage does not provide a full ticker list endpoint
        return []

    @with_backoff()
    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        try:
            data = await self._get({"function": "OVERVIEW", "symbol": instrument_id})
        except httpx.HTTPStatusError:
            return None
        if not data or "Symbol" not in data:
            return None
        return FundamentalsRecord(
            instrument_id=instrument_id,
            asset_class=AssetClass.EQUITY,
            equity=InstrumentEquityRecord(
                instrument_id=instrument_id,
                country_of_incorporation=data.get("Country"),
                shares_outstanding=_safe_int(data.get("SharesOutstanding")),
                float_shares=_safe_int(data.get("SharesFloat")),
            ),
        )


def _safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


connector = AlphaVantageConnector()
