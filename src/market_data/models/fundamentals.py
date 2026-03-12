"""Fundamentals response models — union of asset-class-specific data."""
from __future__ import annotations

from pydantic import BaseModel

from market_data.models.enums import AssetClass
from market_data.models.instrument import (
    InstrumentCommodityRecord,
    InstrumentCryptoRecord,
    InstrumentETFRecord,
    InstrumentEquityRecord,
    InstrumentFXRecord,
)


class FundamentalsRecord(BaseModel):
    instrument_id: str
    asset_class: AssetClass
    crypto: InstrumentCryptoRecord | None = None
    equity: InstrumentEquityRecord | None = None
    etf: InstrumentETFRecord | None = None
    fx: InstrumentFXRecord | None = None
    commodity: InstrumentCommodityRecord | None = None
