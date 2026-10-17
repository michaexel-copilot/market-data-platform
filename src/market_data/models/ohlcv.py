"""OHLCV time-series record model."""
from __future__ import annotations

from datetime import datetime
from math import isfinite

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
    tick_1m: int | None = None
    tick_1h: int | None = None
    tick_1d: int | None = None
    is_aggregated: bool = False

    @field_validator("interval", mode="before")
    @classmethod
    def validate_native_interval(cls, v: str) -> str:
        if v not in _NATIVE_INTERVALS:
            raise ValueError(f"Invalid native interval '{v}'. Must be one of: {sorted(_NATIVE_INTERVALS)}")
        return v


def invalid_ohlcv_reason(record: OHLCVRecord) -> str | None:
    """Return a short reason when an OHLCV record contains impossible values."""
    for field_name in ("open", "high", "low", "close"):
        value = float(getattr(record, field_name))
        if not isfinite(value):
            return f"{field_name} is not finite"
        if value <= 0:
            return f"{field_name} must be > 0"

    if record.high < max(record.open, record.close):
        return "high must be >= open and close"
    if record.low > min(record.open, record.close):
        return "low must be <= open and close"
    if record.low > record.high:
        return "low must be <= high"

    for field_name in ("volume", "vwap", "market_cap"):
        value = getattr(record, field_name)
        if value is None:
            continue
        value = float(value)
        if not isfinite(value):
            return f"{field_name} is not finite"
        if value < 0:
            return f"{field_name} must be >= 0"

    if record.trade_count is not None and record.trade_count < 0:
        return "trade_count must be >= 0"

    return None
