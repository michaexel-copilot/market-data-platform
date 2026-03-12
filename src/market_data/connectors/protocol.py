"""Connector Protocol — structural typing interface for all data source adapters."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from market_data.models.enums import AssetClass, Interval
from market_data.models.fundamentals import FundamentalsRecord
from market_data.models.instrument import InstrumentRecord
from market_data.models.ohlcv import OHLCVRecord


@runtime_checkable
class Connector(Protocol):
    """Protocol that every data source connector must satisfy."""

    name: str
    supported_asset_classes: list[AssetClass]
    supported_intervals: list[Interval]

    async def fetch_ohlcv(
        self,
        instrument_id: str,
        interval: Interval,
        since: datetime,
        until: datetime,
    ) -> list[OHLCVRecord]: ...

    async def fetch_instruments(
        self,
        asset_class: AssetClass,
    ) -> list[InstrumentRecord]: ...

    async def fetch_fundamentals(
        self,
        instrument_id: str,
    ) -> FundamentalsRecord | None: ...
