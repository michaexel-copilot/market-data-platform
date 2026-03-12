"""SEC EDGAR connector — fundamentals (financial statements) for US equities."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx

from market_data.connectors.base import to_float, with_backoff
from market_data.connectors.rate_limiter import RateLimiter
from market_data.models.enums import AssetClass, Interval
from market_data.models.fundamentals import FundamentalsRecord
from market_data.models.instrument import InstrumentEquityRecord, InstrumentRecord
from market_data.models.ohlcv import OHLCVRecord

_BASE_URL = "https://data.sec.gov"
# EDGAR fair-use: max 10 req/sec; be conservative
_RATE = float(os.getenv("SEC_EDGAR_RATE", "5"))
_USER_AGENT = os.getenv("SEC_EDGAR_USER_AGENT", "market-data-platform dev@example.com")


class SECEdgarConnector:
    """SEC EDGAR fundamentals connector — financial statement data only.

    OHLCV is not supported; raises NotImplementedError if called.
    """

    name = "sec_edgar"
    supported_asset_classes = [AssetClass.EQUITY]
    supported_intervals: list[Interval] = []

    def __init__(self) -> None:
        self._rl = RateLimiter(rate=_RATE, burst=_RATE)

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": _USER_AGENT, "Accept": "application/json"}

    async def _get(self, path: str) -> Any:
        await self._rl.acquire()
        async with httpx.AsyncClient(headers=self._headers(), timeout=30) as client:
            resp = await client.get(f"{_BASE_URL}{path}")
            resp.raise_for_status()
            return resp.json()

    async def fetch_ohlcv(
        self,
        instrument_id: str,
        interval: Interval,
        since: datetime,
        until: datetime,
    ) -> list[OHLCVRecord]:
        raise NotImplementedError("SEC EDGAR does not provide OHLCV data")

    @with_backoff()
    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        if asset_class != AssetClass.EQUITY:
            return []
        try:
            data = await self._get("/submissions/CIK0000000000.json")
        except Exception:
            return []
        # Company tickers endpoint
        try:
            tickers_data = await self._get("/files/company_tickers.json")
        except httpx.HTTPStatusError:
            return []
        records: list[InstrumentRecord] = []
        for _, item in tickers_data.items():
            try:
                cik = str(item.get("cik_str", "")).zfill(10)
                records.append(
                    InstrumentRecord(
                        instrument_id=f"CIK{cik}",
                        ticker=(item.get("ticker") or "").upper(),
                        full_name=item.get("title"),
                        asset_class=AssetClass.EQUITY,
                    )
                )
            except Exception:
                continue
        return records

    @with_backoff()
    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        """Fetch company facts for a CIK-based instrument_id (e.g. 'CIK0000320193')."""
        cik = instrument_id.upper().replace("CIK", "").zfill(10)
        try:
            data = await self._get(f"/submissions/CIK{cik}.json")
        except httpx.HTTPStatusError:
            return None
        # Fetch financial facts
        try:
            facts = await self._get(f"/api/xbrl/companyfacts/CIK{cik}.json")
        except httpx.HTTPStatusError:
            facts = {}

        shares_outstanding = _extract_latest_value(
            facts, "us-gaap", "CommonStockSharesOutstanding"
        )
        return FundamentalsRecord(
            instrument_id=instrument_id,
            asset_class=AssetClass.EQUITY,
            equity=InstrumentEquityRecord(
                instrument_id=instrument_id,
                shares_outstanding=int(shares_outstanding) if shares_outstanding else None,
            ),
        )


def _extract_latest_value(facts: dict[str, Any], taxonomy: str, concept: str) -> float | None:
    try:
        units = facts["facts"][taxonomy][concept]["units"]
        # Usually "shares" for share counts
        for unit_data in units.values():
            if not isinstance(unit_data, list):
                continue
            # Get the most recent filed value
            filed = [r for r in unit_data if r.get("form") in ("10-K", "10-Q")]
            if filed:
                return to_float(filed[-1].get("val"))
    except (KeyError, TypeError, IndexError):
        pass
    return None


connector = SECEdgarConnector()
