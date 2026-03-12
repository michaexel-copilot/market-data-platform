"""EODHD connector — equities + crypto OHLCV, all intervals, with fundamentals."""
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

_BASE_URL = "https://eodhd.com/api"
_RATE = float(os.getenv("EODHD_RATE", "5"))

_INTERVAL_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "1h": "1h",
    "1d": "d",
}


class EODHDConnector:
    name = "eodhd"
    supported_asset_classes = [
        AssetClass.EQUITY,
        AssetClass.ETF,
        AssetClass.CRYPTO,
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
        self._api_key = os.getenv("EODHD_API_KEY", "demo")
        self._rl = RateLimiter(rate=_RATE, burst=_RATE)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        await self._rl.acquire()
        p = {"api_token": self._api_key, "fmt": "json", **(params or {})}
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
        period = _INTERVAL_MAP.get(str(interval), "d")
        from_str = to_utc(since).strftime("%Y-%m-%d")
        to_str = to_utc(until).strftime("%Y-%m-%d")
        try:
            if period == "d":
                data = await self._get(
                    f"/eod/{instrument_id}",
                    params={"from": from_str, "to": to_str, "period": "d"},
                )
            else:
                data = await self._get(
                    f"/intraday/{instrument_id}",
                    params={
                        "from": int(to_utc(since).timestamp()),
                        "to": int(to_utc(until).timestamp()),
                        "interval": period,
                    },
                )
        except httpx.HTTPStatusError:
            return []
        if not isinstance(data, list):
            return []
        records: list[OHLCVRecord] = []
        for row in data:
            ts_val = row.get("date") or row.get("datetime") or row.get("timestamp")
            if ts_val is None:
                continue
            if isinstance(ts_val, (int, float)):
                ts = datetime.fromtimestamp(float(ts_val), tz=timezone.utc)
            else:
                ts = datetime.fromisoformat(str(ts_val).replace("Z", "+00:00"))
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
                        close=float(row.get("close") or row.get("adjusted_close", 0) or 0),
                        volume=to_float(row.get("volume")),
                        source=self.name,
                    )
                )
            except Exception:
                continue
        return records

    @with_backoff()
    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        exchange_map = {
            AssetClass.CRYPTO: "CC",
            AssetClass.EQUITY: "US",
            AssetClass.ETF: "US",
        }
        exchange = exchange_map.get(asset_class)
        if not exchange:
            return []
        try:
            data = await self._get(f"/exchange-symbol-list/{exchange}", params={"type": ""})
        except httpx.HTTPStatusError:
            return []
        if not isinstance(data, list):
            return []
        records: list[InstrumentRecord] = []
        for item in data:
            try:
                records.append(
                    InstrumentRecord(
                        instrument_id=f"{item.get('Code','')}.{exchange}",
                        ticker=(item.get("Code") or "").upper(),
                        full_name=item.get("Name"),
                        asset_class=asset_class,
                        exchange=exchange,
                    )
                )
            except Exception:
                continue
        return records

    @with_backoff()
    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        try:
            data = await self._get(f"/fundamentals/{instrument_id}")
        except httpx.HTTPStatusError:
            return None
        general = data.get("General", {})
        asset_type = (general.get("Type") or "").lower()
        asset_class = AssetClass.EQUITY if "stock" in asset_type or "equity" in asset_type else AssetClass.ETF
        highlights = data.get("Highlights", {})
        shares = data.get("SharesStats", {})
        return FundamentalsRecord(
            instrument_id=instrument_id,
            asset_class=asset_class,
            equity=InstrumentEquityRecord(
                instrument_id=instrument_id,
                isin=general.get("ISIN"),
                cusip=general.get("CUSIP"),
                country_of_incorporation=general.get("CountryISO"),
                shares_outstanding=_safe_int(shares.get("SharesOutstanding")),
                float_shares=_safe_int(shares.get("SharesFloat")),
            ),
        )


def _safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


connector = EODHDConnector()
