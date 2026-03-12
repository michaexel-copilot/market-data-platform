"""Shared enumerations."""
from enum import StrEnum


class AssetClass(StrEnum):
    CRYPTO    = "crypto"
    EQUITY    = "equity"
    ETF       = "etf"
    FX        = "fx"
    COMMODITY = "commodity"
    INDEX     = "index"
    FUTURE    = "future"


class Interval(StrEnum):
    ONE_MIN   = "1m"
    FIVE_MIN  = "5m"
    ONE_HOUR  = "1h"
    ONE_DAY   = "1d"
    ONE_WEEK  = "1w"    # derived view only
    ONE_MONTH = "1mo"   # derived view only

    @property
    def is_native(self) -> bool:
        return self in (Interval.ONE_MIN, Interval.FIVE_MIN, Interval.ONE_HOUR, Interval.ONE_DAY)

    @property
    def is_derived(self) -> bool:
        return self in (Interval.ONE_WEEK, Interval.ONE_MONTH)


class IdType(StrEnum):
    ISIN             = "isin"
    CUSIP            = "cusip"
    FIGI             = "figi"
    COMPOSITE_FIGI   = "composite_figi"
    MIC_CODE         = "mic_code"
    COINGECKO_ID     = "coingecko_id"
    CMC_ID           = "cmc_id"
    COINCODEX_ID     = "coincodex_id"
    CONTRACT_ADDRESS = "contract_address"
    TICKER_EXCHANGE  = "ticker_exchange"
