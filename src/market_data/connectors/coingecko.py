"""CoinGecko connector — crypto OHLCV + instrument list + fundamentals."""
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

# Free tier: 10–50 req/min; paid Pro tier unlocks higher limits
_RATE = float(os.getenv("COINGECKO_RATE", "10"))
_BASE_URL = "https://api.coingecko.com/api/v3"
_PRO_BASE_URL = "https://pro-api.coingecko.com/api/v3"

# Map native intervals to CoinGecko OHLC days parameter
_INTERVAL_TO_DAYS: dict[str, str] = {
    "1d": "max",
    "1h": "30",    # hourly data for last 30 days
    "5m": "1",     # 5-min granularity for last 1 day
    "1m": "1",     # 1-min via /market_chart (closest approximation)
}


class CoinGeckoConnector:
    name = "coingecko"
    supported_asset_classes = [AssetClass.CRYPTO]
    supported_intervals = [
        Interval.ONE_DAY,
        Interval.ONE_HOUR,
        Interval.FIVE_MIN,
        Interval.ONE_MIN,
    ]

    def __init__(self) -> None:
        api_key = os.getenv("COINGECKO_API_KEY", "")
        self._headers: dict[str, str] = {}
        if api_key:
            self._base_url = _PRO_BASE_URL
            self._headers["x-cg-pro-api-key"] = api_key
        else:
            self._base_url = _BASE_URL
            self._headers["x-cg-demo-api-key"] = os.getenv("COINGECKO_DEMO_KEY", "")
        self._rl = RateLimiter(rate=_RATE, burst=_RATE)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        await self._rl.acquire()
        async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
            resp = await client.get(f"{self._base_url}{path}", params=params)
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

        if interval in (Interval.ONE_DAY, Interval.ONE_HOUR):
            # /coins/{id}/market_chart/range returns lists of [ts_ms, value]
            data = await self._get(
                f"/coins/{instrument_id}/market_chart/range",
                params={"vs_currency": "usd", "from": since_ts, "to": until_ts},
            )
            prices: list[list[float]] = data.get("prices", [])
            vols: list[list[float]] = data.get("total_volumes", [])
            mcaps: list[list[float]] = data.get("market_caps", [])
            vol_map = {int(r[0]): r[1] for r in vols}
            mc_map = {int(r[0]): r[1] for r in mcaps}
            records: list[OHLCVRecord] = []
            for ts_ms, price in prices:
                ts_ms = int(ts_ms)
                ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                records.append(
                    OHLCVRecord(
                        instrument_id=instrument_id,
                        interval=interval,
                        ts=ts,
                        open=price,
                        high=price,
                        low=price,
                        close=price,
                        volume=to_float(vol_map.get(ts_ms)),
                        market_cap=to_float(mc_map.get(ts_ms)),
                        source=self.name,
                    )
                )
            return records

        # For sub-hourly, use /coins/{id}/ohlc (only daily/4h/1h available on free tier)
        # Return empty for 1m/5m if not available at this granularity
        return []

    @with_backoff()
    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        if asset_class != AssetClass.CRYPTO:
            return []
        data = await self._get("/coins/list", params={"include_platform": "false"})
        records: list[InstrumentRecord] = []
        for item in data:
            try:
                records.append(
                    InstrumentRecord(
                        instrument_id=item["id"],
                        ticker=item.get("symbol", "").upper(),
                        full_name=item.get("name", ""),
                        asset_class=AssetClass.CRYPTO,
                    )
                )
            except Exception:
                continue
        return records

    @with_backoff()
    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        try:
            data = await self._get(
                f"/coins/{instrument_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "true",
                    "community_data": "false",
                    "developer_data": "false",
                },
            )
        except httpx.HTTPStatusError:
            return None
        md = data.get("market_data", {})
        from market_data.models.instrument import InstrumentCryptoRecord
        return FundamentalsRecord(
            instrument_id=instrument_id,
            asset_class=AssetClass.CRYPTO,
            crypto=InstrumentCryptoRecord(
                instrument_id=instrument_id,
                total_supply=to_float(md.get("total_supply")),
                max_supply=to_float(md.get("max_supply")),
                circulating_supply=to_float(md.get("circulating_supply")),
                whitepaper_url=(
                    (data.get("links") or {}).get("whitepaper") or None
                ),
                github_url=(
                    ((data.get("links") or {}).get("repos_url") or {}).get("github", [None])[0]
                ),
            ),
        )


connector = CoinGeckoConnector()
