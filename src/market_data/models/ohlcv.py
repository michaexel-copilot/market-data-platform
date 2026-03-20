"""OHLCV time-series record model."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

from market_data.models.enums import Interval

_NATIVE_INTERVALS = {"1m", "5m", "1h", "1d"}
_ALL_INTERVALS = {"1m", "5m", "1h", "1d", "1w", "1mo"}


class OHLCVRecord(BaseModel):
    instrument_id: str
    interval: Interval
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    vwap: float | None = None
    trade_count: int | None = None
    market_cap: float | None = None
    source: str
    ingested_at: datetime | None = None
    tick_1h: int | None = None
    tick_1d: int | None = None

    @field_validator("interval", mode="before")
    @classmethod
    def validate_native_interval(cls, v: str) -> str:
        if v not in _NATIVE_INTERVALS:
            raise ValueError(f"Invalid native interval '{v}'. Must be one of: {sorted(_NATIVE_INTERVALS)}")
        return v
