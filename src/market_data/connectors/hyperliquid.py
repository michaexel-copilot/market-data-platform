"""Hyperliquid connector — fetches perpetual pairs metadata (no OHLCV)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from market_data.models.enums import AssetClass, Interval
from market_data.models.fundamentals import FundamentalsRecord
from market_data.models.instrument import HLPairRecord, InstrumentRecord
from market_data.models.ohlcv import OHLCVRecord

logger = logging.getLogger(__name__)

_MAINNET_URL = "https://api.hyperliquid.xyz/info"
_TESTNET_URL = "https://api.hyperliquid-testnet.xyz/info"


def _strip_k_prefix(symbol: str) -> str:
    """Strip the Hyperliquid K-prefix convention (KPEPE -> PEPE)."""
    if symbol.startswith("K") and len(symbol) > 1 and symbol[1:].isalpha():
        return symbol[1:]
    return symbol


class HyperliquidConnector:
    """Hyperliquid perpetual pairs connector.

    Implements fetch_instruments (returns InstrumentRecord for matched instruments)
    and fetch_hl_pairs (returns raw HLPairRecord list).
    OHLCV is not supported; raises NotImplementedError if called.
    """

    name = "hyperliquid"
    supported_asset_classes = [AssetClass.CRYPTO]
    supported_intervals: list[Interval] = []

    async def fetch_ohlcv(
        self,
        instrument_id: str,
        interval: Interval,
        since: datetime,
        until: datetime,
    ) -> list[OHLCVRecord]:
        raise NotImplementedError("Hyperliquid does not provide historical OHLCV data")

    async def fetch_hl_pairs(self, network: str = "mainnet") -> list[HLPairRecord]:
        """Fetch perpetual pairs from the Hyperliquid API for the given network.

        Args:
            network: "mainnet" or "testnet"

        Returns:
            List of HLPairRecord with normalised fields.
        """
        url = _MAINNET_URL if network == "mainnet" else _TESTNET_URL
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json={"type": "meta"})
            resp.raise_for_status()
            data = resp.json()

        pairs: list[HLPairRecord] = []
        for asset in data.get("universe", []):
            raw_name: str = asset.get("name", "")
            hl_symbol = f"{raw_name}/USDC:USDC"
            base_ticker = _strip_k_prefix(raw_name)
            sz_decimals: int = asset.get("szDecimals", 0)
            lot_size = 10 ** (-sz_decimals) if sz_decimals >= 0 else 1.0
            # max_leverage comes from the "maxLeverage" field
            max_leverage = float(asset.get("maxLeverage", 1))
            # Hyperliquid API doesn't expose tick_size directly in /meta;
            # use a sentinel of 0.0 — callers should treat this as "not available"
            tick_size = 0.0

            pairs.append(HLPairRecord(
                hl_symbol=hl_symbol,
                base_ticker=base_ticker,
                lot_size=lot_size,
                tick_size=tick_size,
                max_leverage=max_leverage,
            ))

        return pairs

    async def fetch_instruments(self, asset_class: AssetClass) -> list[InstrumentRecord]:
        """Return InstrumentRecord stubs for each HL mainnet pair (no DB reconciliation here)."""
        if asset_class not in self.supported_asset_classes:
            return []
        pairs = await self.fetch_hl_pairs("mainnet")
        records: list[InstrumentRecord] = []
        for pair in pairs:
            records.append(InstrumentRecord(
                instrument_id=pair.base_ticker,  # placeholder; real ID requires DB lookup
                ticker=pair.base_ticker,
                asset_class=AssetClass.CRYPTO,
            ))
        return records

    async def fetch_fundamentals(self, instrument_id: str) -> FundamentalsRecord | None:
        return None


def reconcile_hl_pairs(
    pairs: list[HLPairRecord],
    conn: object,
) -> list[tuple[str, HLPairRecord]]:
    """Match each HLPairRecord to an instrument_id in the canonical registry.

    Returns a list of (instrument_id, HLPairRecord) for matched pairs.
    Unmatched pairs are logged at WARNING level and excluded.

    Args:
        pairs: List of HLPairRecord objects from fetch_hl_pairs.
        conn: An active psycopg/DuckDB connection with an `execute` method.
    """
    if not pairs:
        return []

    tickers = [p.base_ticker.upper() for p in pairs]
    rows = conn.execute(  # type: ignore[union-attr]
        "SELECT instrument_id, upper(ticker) FROM instruments WHERE upper(ticker) = ANY(%s)",
        (tickers,),
    ).fetchall()

    ticker_to_id: dict[str, str] = {row[1]: row[0] for row in rows}

    result: list[tuple[str, HLPairRecord]] = []
    for pair in pairs:
        key = pair.base_ticker.upper()
        if key in ticker_to_id:
            result.append((ticker_to_id[key], pair))
        else:
            logger.warning("Hyperliquid pair '%s' (ticker '%s') not found in instrument registry",
                           pair.hl_symbol, pair.base_ticker)

    return result


connector = HyperliquidConnector()
