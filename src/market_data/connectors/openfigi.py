"""OpenFIGI connector — reference/instrument identification only (no OHLCV)."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx

from market_data.connectors.base import with_backoff
from market_data.connectors.rate_limiter import RateLimiter
from market_data.models.enums import AssetClass, IdType, Interval
from market_data.models.fundamentals import FundamentalsRecord
from market_data.models.instrument import IdentifierRecord, InstrumentRecord
from market_data.models.ohlcv import OHLCVRecord

_BASE_URL = "https://api.openfigi.com/v3"
_RATE = float(os.getenv("OPENFIGI_RATE", "2"))


class OpenFIGIConnector:
    """Reference data connector — maps identifiers to FIGI.

    OHLCV is not supported; raises NotImplementedError if called.
    """

    name = "openfigi"
    supported_asset_classes = [
        AssetClass.EQUITY,
        AssetClass.ETF,
        AssetClass.FUTURE,
        AssetClass.COMMODITY,
    ]
    supported_intervals: list[Interval] = []

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENFIGI_API_KEY", "")
        self._rl = RateLimiter(rate=_RATE, burst=_RATE)

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            h["X-OPENFIGI-APIKEY"] = self._api_key
        return h

    async def fetch_ohlcv(
        self,
        instrument_id: str,
        interval: Interval,
        since: datetime,
        until: datetime,
    ) -> list[OHLCVRecord]:
        raise NotImplementedError("OpenFIGI does not provide OHLCV data")

    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        # OpenFIGI is a lookup service, not a listing service
        return []

    @with_backoff()
    async def map_identifier(
        self,
        id_type: IdType,
        id_value: str,
    ) -> list[IdentifierRecord]:
        """Map an external identifier (ISIN, CUSIP, etc.) to FIGI identifiers."""
        await self._rl.acquire()
        id_type_map = {
            IdType.ISIN: "ID_ISIN",
            IdType.CUSIP: "ID_CUSIP",
            IdType.FIGI: "ID_BB_GLOBAL",
        }
        openfigi_type = id_type_map.get(id_type)
        if not openfigi_type:
            return []
        payload = [{"idType": openfigi_type, "idValue": id_value}]
        async with httpx.AsyncClient(headers=self._headers(), timeout=30) as client:
            resp = await client.post(f"{_BASE_URL}/mapping", json=payload)
            resp.raise_for_status()
            data = resp.json()
        records: list[IdentifierRecord] = []
        for batch in data:
            for item in batch.get("data", []):
                figi = item.get("figi")
                if figi:
                    records.append(
                        IdentifierRecord(
                            instrument_id=id_value,
                            id_type=IdType.FIGI,
                            id_value=figi,
                        )
                    )
        return records

    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        return None


connector = OpenFIGIConnector()
