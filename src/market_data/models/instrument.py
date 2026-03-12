"""Instrument data models."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from market_data.models.enums import AssetClass, IdType


class IdentifierRecord(BaseModel):
    instrument_id: str
    id_type: IdType
    id_value: str
    chain: str | None = None


class InstrumentRecord(BaseModel):
    instrument_id: str
    ticker: str
    full_name: str | None = None
    description: str | None = None
    asset_class: AssetClass
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    quote_currency: str | None = None
    launch_date: date | None = None
    is_active: bool = True
    logo_url: str | None = None
    website_url: str | None = None
    data_sources: list[str] | None = None
    first_seen_at: datetime | None = None
    last_updated_at: datetime | None = None


class InstrumentCryptoRecord(BaseModel):
    instrument_id: str
    blockchain_network: str | None = None
    consensus_mechanism: str | None = None
    total_supply: float | None = None
    max_supply: float | None = None
    circulating_supply: float | None = None
    decimals: int | None = None
    whitepaper_url: str | None = None
    github_url: str | None = None


class InstrumentEquityRecord(BaseModel):
    instrument_id: str
    isin: str | None = None
    cusip: str | None = None
    figi: str | None = None
    composite_figi: str | None = None
    mic_code: str | None = None
    sic_code: str | None = None
    country_of_incorporation: str | None = None  # ISO 3166-1 alpha-2
    shares_outstanding: int | None = None
    float_shares: int | None = None


class InstrumentETFRecord(BaseModel):
    instrument_id: str
    tracking_index: str | None = None
    expense_ratio: float | None = None
    aum: float | None = None
    fund_type: str | None = None


class InstrumentFXRecord(BaseModel):
    instrument_id: str
    base_currency: str | None = None
    quote_currency: str | None = None
    pip_size: float | None = None
    session_type: str | None = None


class InstrumentCommodityRecord(BaseModel):
    instrument_id: str
    unit_of_measure: str | None = None
    contract_size: float | None = None
    delivery_month: str | None = None
