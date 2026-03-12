"""Yahoo Finance connector — equities + ETFs via yfinance (fallback/secondary source)."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import yfinance as yf

from market_data.connectors.base import to_float, to_utc
from market_data.models.enums import AssetClass, Interval
from market_data.models.fundamentals import FundamentalsRecord
from market_data.models.instrument import InstrumentEquityRecord, InstrumentRecord
from market_data.models.ohlcv import OHLCVRecord

# yfinance interval strings
_INTERVAL_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "1h": "1h",
    "1d": "1d",
}


class YahooFinanceConnector:
    name = "yahoo_finance"
    supported_asset_classes = [
        AssetClass.EQUITY,
        AssetClass.ETF,
        AssetClass.CRYPTO,
        AssetClass.INDEX,
    ]
    supported_intervals = [
        Interval.ONE_MIN,
        Interval.FIVE_MIN,
        Interval.ONE_HOUR,
        Interval.ONE_DAY,
    ]

    async def fetch_ohlcv(
        self,
        instrument_id: str,
        interval: Interval,
        since: datetime,
        until: datetime,
    ) -> list[OHLCVRecord]:
        yf_interval = _INTERVAL_MAP.get(str(interval), "1d")
        since_utc = to_utc(since)
        until_utc = to_utc(until)

        def _download() -> Any:
            ticker = yf.Ticker(instrument_id)
            return ticker.history(
                start=since_utc,
                end=until_utc,
                interval=yf_interval,
                auto_adjust=True,
            )

        df = await asyncio.get_event_loop().run_in_executor(None, _download)
        if df is None or df.empty:
            return []

        records: list[OHLCVRecord] = []
        for ts, row in df.iterrows():
            # ts is a pandas Timestamp; convert to UTC datetime
            try:
                ts_dt = ts.to_pydatetime()
                if ts_dt.tzinfo is None:
                    import pytz
                    ts_dt = pytz.utc.localize(ts_dt)
                records.append(
                    OHLCVRecord(
                        instrument_id=instrument_id,
                        interval=interval,
                        ts=ts_dt,
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=to_float(row.get("Volume")),
                        source=self.name,
                    )
                )
            except Exception:
                continue
        return records

    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        # yfinance does not provide bulk listing; returns empty
        return []

    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        def _info() -> dict[str, Any]:
            return yf.Ticker(instrument_id).info or {}

        info = await asyncio.get_event_loop().run_in_executor(None, _info)
        if not info:
            return None
        quote_type = (info.get("quoteType") or "").upper()
        asset_class = AssetClass.ETF if quote_type == "ETF" else AssetClass.EQUITY
        return FundamentalsRecord(
            instrument_id=instrument_id,
            asset_class=asset_class,
            equity=InstrumentEquityRecord(
                instrument_id=instrument_id,
                isin=info.get("isin"),
                country_of_incorporation=info.get("country"),
                shares_outstanding=_safe_int(info.get("sharesOutstanding")),
                float_shares=_safe_int(info.get("floatShares")),
            ),
        )


def _safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


connector = YahooFinanceConnector()
