"""
hl_order: place Hyperliquid perpetual orders via the local hl_client library.

Credentials are loaded from a .env file in the project root:
  HL_MASTER_PRIVATE_KEY / HL_MASTER_WALLET_ADDRESS  — mainnet
  HL_TEST_PRIVATE_KEY   / HL_TEST_WALLET_ADDRESS    — testnet
"""
from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).parent
# Single source of truth: hl_client project .env
_HL_ENV = Path("/work/projekte/hyperliquid-python/hl_client/.env")

# ---------------------------------------------------------------------------
# Pairs metadata — loaded once at module level
# ---------------------------------------------------------------------------

HL_TESTNET_PAIRS_CSV = ROOT / "hl_testnet_pairs.csv"
HL_MAINNET_PAIRS_CSV = Path(os.environ.get("HL_PAIRS_CSV", "/mnt/ds420/data/hyperliquid/hl-main-pairs.csv"))


@dataclass
class PairMeta:
    hl_symbol: str    # e.g. "BTC/USDC:USDC"
    lot_size: float
    max_leverage: float


def _load_pairs(csv_path: Path) -> dict[str, PairMeta]:
    """Return {base_symbol_upper: PairMeta} from a Hyperliquid pairs CSV."""
    result: dict[str, PairMeta] = {}
    if not csv_path.exists():
        return result
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            base = row["base"].upper()
            result[base] = PairMeta(
                hl_symbol=row["symbol"],
                lot_size=float(row["lot_size"]),
                max_leverage=float(row["max_leverage"]),
            )
    return result


_TESTNET_META: dict[str, PairMeta] = _load_pairs(HL_TESTNET_PAIRS_CSV)
_MAINNET_META: dict[str, PairMeta] = _load_pairs(HL_MAINNET_PAIRS_CSV)


def get_pair_meta(base_symbol: str, *, testnet: bool) -> PairMeta | None:
    meta = _TESTNET_META if testnet else _MAINNET_META
    return meta.get(base_symbol.upper())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lot_decimals(lot_size: float) -> int:
    """Number of decimal places for amount rounding, derived from lot_size.

    Examples: 0.01 → 2,  0.001 → 3,  1.0 → 0,  10.0 → 0
    """
    if lot_size >= 1.0:
        return 0
    return max(0, -int(math.floor(math.log10(lot_size))))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def place_order(
    *,
    base_symbol: str,
    side: Literal["buy", "sell"],
    order_type: Literal["market", "limit"],
    size_usd: float,
    leverage: int,
    margin_type: Literal["cross", "isolated"],
    reduce_only: bool,
    tp_price: float | None,
    sl_price: float | None,
    limit_price: float | None,
    testnet: bool,
) -> dict:
    """Place a perpetual order on Hyperliquid.

    Returns a dict:
      ok           bool
      order_id     str               (on success)
      tp_order_id  str | None
      sl_order_id  str | None
      error        str               (on failure)
    """
    try:
        from hl_client import HLClient  # imported lazily so module loads fast
    except ImportError:
        return {"ok": False, "error": "Order placement is not available in this deployment (hl_client is not installed)"}

    # AFTER — reads file fresh every call, immune to os.environ caching
    creds = dotenv_values(_HL_ENV)

    if testnet:
        private_key    = creds.get("HL_TEST_PRIVATE_KEY", "")
        wallet_address = creds.get("HL_TEST_WALLET_ADDRESS", "")
    else:
        private_key    = creds.get("HL_MASTER_PRIVATE_KEY", "")
        wallet_address = creds.get("HL_MASTER_WALLET_ADDRESS", "")

    if not private_key or private_key.startswith("0xYOUR"):
        network_label = "testnet" if testnet else "mainnet"
        return {"ok": False, "error": f"No credentials set for {network_label} — fill in .env"}

    meta = get_pair_meta(base_symbol, testnet=testnet)
    if meta is None:
        return {"ok": False, "error": f"Symbol {base_symbol!r} not found in pairs metadata"}

    async with HLClient(private_key=private_key, wallet_address=wallet_address, testnet=testnet) as client:

        # 1. Set leverage
        try:
            await client._exchange.set_leverage(
                leverage, meta.hl_symbol, params={"marginMode": margin_type}
            )
        except Exception as exc:
            return {"ok": False, "error": f"set_leverage failed: {exc}"}

        # 2. Determine order amount from current ticker price
        try:
            ticker = await client.fetch_ticker(meta.hl_symbol)
            current_price = ticker.last
        except Exception as exc:
            return {"ok": False, "error": f"fetch_ticker failed: {exc}"}

        decimals = _lot_decimals(meta.lot_size)
        amount = round(size_usd / current_price, decimals)
        if amount <= 0:
            return {
                "ok": False,
                "error": f"Computed amount is zero — size_usd {size_usd} too small for lot_size {meta.lot_size}",
            }

        # 3. Place main order via hl_client API
        try:
            if reduce_only:
                # reduce-only needs params passed through the raw exchange call
                raw = await client._exchange.create_order(
                    meta.hl_symbol, order_type, side, amount,
                    limit_price if order_type == "limit" else None,
                    {"reduceOnly": True},
                )
                main_id = raw.get("id", "?")
            elif order_type == "market":
                order = await client.place_order(meta.hl_symbol, side, amount,
                                                  order_type="market", price=current_price)
                main_id = order.id
            else:
                order = await client.place_limit_order(meta.hl_symbol, side, amount, limit_price)  # type: ignore[arg-type]
                main_id = order.id
        except Exception as exc:
            return {"ok": False, "error": f"Main order failed: {exc}"}

        result: dict = {"ok": True, "order_id": main_id, "tp_order_id": None, "sl_order_id": None}

        # 4. TP / SL bracket orders (only when not reduce-only)
        if not reduce_only and (tp_price is not None or sl_price is not None):
            close_side: Literal["buy", "sell"] = "sell" if side == "buy" else "buy"

            if tp_price is not None:
                try:
                    tp_raw = await client._exchange.create_order(
                        meta.hl_symbol, "limit", close_side, amount, tp_price,
                        {"reduceOnly": True},
                    )
                    result["tp_order_id"] = tp_raw.get("id")
                except Exception as exc:
                    print(f"[hl_order] TP order failed (non-fatal): {exc}")

            if sl_price is not None:
                try:
                    sl_raw = await client._exchange.create_order(
                        meta.hl_symbol, "stop", close_side, amount, sl_price,
                        {"reduceOnly": True, "triggerPrice": sl_price},
                    )
                    result["sl_order_id"] = sl_raw.get("id")
                except Exception as exc:
                    print(f"[hl_order] SL order failed (non-fatal): {exc}")

        return result
