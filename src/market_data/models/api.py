"""API request/response models shared across REST, JSON-RPC, and gRPC."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from market_data.models.enums import AssetClass, Interval

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    page: int
    page_size: int
    items: list[T]
    next_page: int | None = None


class HLMetadata(BaseModel):
    """Hyperliquid-specific trading metadata embedded in instrument list responses."""
    hl_symbol: str
    lot_size: float
    tick_size: float
    max_leverage: float


class InstrumentListRequest(BaseModel):
    asset_class: AssetClass | None = None
    is_active: bool = True
    q: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class OHLCVRequest(BaseModel):
    symbol: str
    interval: Interval
    since: str | None = None   # ISO 8601
    until: str | None = None   # ISO 8601
    asset_class: AssetClass | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=1000, ge=1, le=5000)


class ErrorResponse(BaseModel):
    code: str
    message: str


class SymbolNotFoundError(Exception):
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__(f"Symbol not found: {symbol!r}")


class AmbiguousSymbolError(Exception):
    def __init__(self, symbol: str, matches: list[str]) -> None:
        self.symbol = symbol
        self.matches = matches
        super().__init__(f"Ambiguous symbol {symbol!r}: matches {matches}")
