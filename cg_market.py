"""
cg_market: Fetch ATH / ATL market data from the CoinGecko free API.

No API key required.  Rate limit ~30 req/min on free tier.
Data is cached daily to cache/cg_market/{SYM}_{DATE}.json.
"""
import json
from datetime import date
from pathlib import Path

import requests

try:
    from draw_chart import CG_COIN_ID_MAP as _CG_OHLC_MAP  # noqa: PLC0415
except ImportError:
    _CG_OHLC_MAP = {}

ROOT      = Path(__file__).parent
CACHE_DIR = ROOT / "cache" / "cg_market"

CG_COINS_URL = "https://api.coingecko.com/api/v3/coins/{id}"

# ---------------------------------------------------------------------------
# HL symbol → CoinGecko coin ID for ATH/ATL lookups.
# Inherits all OHLC-routed entries from draw_chart.CG_COIN_ID_MAP, then adds
# every well-known symbol that routes via Yahoo Finance for OHLC but whose
# CoinGecko ID is unambiguous.
# ---------------------------------------------------------------------------
_CG_ID_MAP: dict[str, str] = {
    # ── inherited from draw_chart (OHLC-routed symbols) ──────────────────
    **_CG_OHLC_MAP,
    # ── K-scale symbols not in OHLC map ──────────────────────────────────
    "KBONK":    "bonk",
    "KDOGS":    "dogs-2",
    "KFLOKI":   "floki",
    "KLUNC":    "terra-luna",
    "KNEIRO":   "neiro-ethereum",
    "KSHIB":    "shiba-inu",
    # ── Layer 1 ───────────────────────────────────────────────────────────
    "BTC":      "bitcoin",
    "ETH":      "ethereum",
    "SOL":      "solana",
    "BNB":      "binancecoin",
    "XRP":      "ripple",
    "ADA":      "cardano",
    "AVAX":     "avalanche-2",
    "DOT":      "polkadot",
    "NEAR":     "near",
    "APT":      "aptos",
    "ATOM":     "cosmos",
    "ICP":      "internet-computer",
    "TRX":      "tron",
    "HBAR":     "hedera-hashgraph",
    "XLM":      "stellar",
    "XMR":      "monero",
    "LTC":      "litecoin",
    "BCH":      "bitcoin-cash",
    "BSV":      "bitcoin-cash-sv",
    "DASH":     "dash",
    "ZEC":      "zcash",
    "NEO":      "neo",
    "ETC":      "ethereum-classic",
    "CELO":     "celo",
    "CFX":      "conflux-token",
    "IOTA":     "iota",
    "KAS":      "kaspa",
    "MINA":     "mina-protocol",
    "ALGO":     "algorand",
    "TON":      "the-open-network",
    "STX":      "blockstack",
    "BERA":     "berachain-bera",
    "MOVE":     "movement-2",
    "IP":       "story-2",
    # ── Layer 2 / scaling ────────────────────────────────────────────────
    "ARB":      "arbitrum",
    "OP":       "optimism",
    "STRK":     "starknet",
    "MANTA":    "manta-network",
    "BLAST":    "blast-2",
    "ZETA":     "zetachain",
    "SCR":      "scroll",
    "DYM":      "dymension",
    "CANTO":    "canto",
    "OMNI":     "omni-network",
    "NTRN":     "neutron-3",
    "INIT":     "initia",
    # ── DeFi ─────────────────────────────────────────────────────────────
    "AAVE":     "aave",
    "UNI":      "uniswap",
    "CRV":      "curve-dao-token",
    "SNX":      "havven",
    "MKR":      "maker",
    "LDO":      "lido-dao",
    "GMX":      "gmx",
    "SUSHI":    "sushi",
    "PENDLE":   "pendle",
    "DYDX":     "dydx-chain",
    "ENA":      "ethena",
    "AERO":     "aerodrome-finance",
    "CAKE":     "pancakeswap-token",
    "BNT":      "bancor",
    "FXS":      "frax-share",
    "RDNT":     "radiant-capital",
    "BADGER":   "badger-dao",
    "USUAL":    "usual",
    "ONDO":     "ondo-finance",
    "MAV":      "maverick-protocol",
    "LISTA":    "lista-dao",
    "RESOLV":   "resolv-lst",
    "REZ":      "renzo-protocol",
    # ── Oracles / infra ──────────────────────────────────────────────────
    "LINK":     "chainlink",
    "PYTH":     "pyth-network",
    "GRT":      "the-graph",
    "TRB":      "tellor",
    "FET":      "fetch-ai",
    "EIGEN":    "eigenlayer",
    "INJ":      "injective-protocol",
    "SEI":      "sei-network",
    "TIA":      "celestia",
    "RUNE":     "thorchain",
    "W":        "wormhole",
    "RENDER":   "render-token",
    # ── Storage / compute ────────────────────────────────────────────────
    "FIL":      "filecoin",
    "AR":       "arweave",
    "IO":       "io-net",
    # ── NFT / Gaming ─────────────────────────────────────────────────────
    "AXS":      "axie-infinity",
    "SAND":     "the-sandbox",
    "ILV":      "illuvium",
    "GALA":     "gala",
    "BIGTIME":  "big-time",
    "PIXEL":    "pixels",
    "MAVIA":    "heroes-of-mavia",
    "YGG":      "yield-guild-games",
    # ── Meme coins ───────────────────────────────────────────────────────
    "DOGE":     "dogecoin",
    "SHIB":     "shiba-inu",
    "FLOKI":    "floki",
    "PEPE":     "pepe",
    "WIF":      "dogwifcoin",
    "BRETT":    "based-brett",
    "POPCAT":   "popcat",
    "MOODENG":  "moo-deng",
    "GOAT":     "goatseus-maximus",
    "TRUMP":    "official-trump",
    "MELANIA":  "melania-meme",
    "PNUT":     "peanut-the-squirrel",
    "TURBO":    "turbo-2",
    "BOME":     "book-of-meme",
    "MEME":     "memecoin",
    "CHILLGUY": "chillguy",
    "ZEREBRO":  "zerebro",
    "FARTCOIN": "fartcoin",
    "GRIFFAIN": "griffain",
    "NOT":      "notcoin",
    "HMSTR":    "hamster-kombat",
    "CATI":     "catizen",
    "MEW":      "cat-in-a-dogs-world",
    "MYRO":     "myro",
    "PEOPLE":   "constitutiondao",
    "JELLY":    "jelly-my-jelly",
    "NEIROETH": "neiro-ethereum",
    # ── Governance / misc ────────────────────────────────────────────────
    "ENS":      "ethereum-name-service",
    "UMA":      "uma",
    "OGN":      "origin-protocol",
    "ORBS":     "orbs",
    "LIT":      "litentry",
    "LOOM":     "loom-network-new",
    "BLZ":      "bluzelle",
    "RSR":      "reserve-rights-token",
    "REQ":      "request-network",
    "RLB":      "rollbit-coin",
    "UNIBOT":   "unibot",
    "BANANA":   "banana-gun",
    "SUPER":    "superfarm",
    "BLUR":     "blur",
    "DOOD":     "doodles-2",
    "FTT":      "ftx-token",
    "FTM":      "fantom",
    "SKY":      "sky-governance",
    "OM":       "mantra-dao",
    "BIO":      "bio-protocol",
    "ETHFI":    "ether-fi",
    "PAXG":     "pax-gold",
    "ORDI":     "ordi",
    "TNSR":     "tensor",
    "JTO":      "jito-governance-token",
    "JUP":      "jupiter-exchange-solana",
    "PYTH":     "pyth-network",
    "VIRTUAL":  "virtual-protocol",
    "AI16Z":    "ai16z",
    "AIXBT":    "aixbt-by-virtuals",
    "APE":      "apecoin",
    "SAGA":     "saga-2",
    "CYBER":    "cyberconnect-2",
    "STRAX":    "stratis",
    "XAI":      "xai-blockchain",
    "KAITO":    "kaito",
    "ACE":      "fusionist",
    "ALT":      "altlayer",
    "ENA":      "ethena",
    "GMT":      "stepn",
    "HEMI":     "hemi-network",
    "GRASS":    "grass",
    "ME":       "magic-eden-2",
    "WLD":      "worldcoin-wld",
    "LAYER":    "solayer",
    "PURR":     "purr",
    "OMNI":     "omni-network",
    "AI":       "sleepless-ai",
    "ANIME":    "anime-2",
    "PANDORA":  "pandora",
    "USTC":     "terrausd",
    "NIL":      "nil",
    "HYPER":    "hyper",
    "NFTI":     "nft-index",
    "GAS":      "neo-gas",
    "BABY":     "babydoge-2",
    "ZEN":      "horizen",
    "XPL":      "xpla",
}


# ---------------------------------------------------------------------------
# In-process cache
# ---------------------------------------------------------------------------
_mem_cache: dict[str, dict] = {}

_EMPTY = {"ath": None, "atl": None, "ath_date": None, "atl_date": None}


def _cache_path(sym: str) -> Path:
    return CACHE_DIR / f"{sym}_{date.today()}.json"


def _load_disk(sym: str) -> dict | None:
    p = _cache_path(sym)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None


def _save_disk(sym: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(sym).write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_cg_market(hl_symbol: str) -> dict:
    """
    Return a dict with ATH/ATL data for the given HL symbol.

    Keys: ath, atl (float|None), ath_date, atl_date (str|None, YYYY-MM-DD).
    Returns all-None dict for unknown symbols (graceful degradation).
    """
    sym = hl_symbol.upper()
    cg_id = _CG_ID_MAP.get(sym)
    if not cg_id:
        return {**_EMPTY}

    if sym in _mem_cache:
        return _mem_cache[sym]

    disk = _load_disk(sym)
    if disk is not None:
        _mem_cache[sym] = disk
        return disk

    try:
        resp = requests.get(
            CG_COINS_URL.format(id=cg_id),
            params={
                "localization":    "false",
                "tickers":         "false",
                "market_data":     "true",
                "community_data":  "false",
                "developer_data":  "false",
                "sparkline":       "false",
            },
            timeout=15,
        )
        resp.raise_for_status()
        md = resp.json().get("market_data", {})

        def _date(raw: str | None) -> str | None:
            return raw[:10] if raw else None

        result = {
            "ath":      (md.get("ath") or {}).get("usd"),
            "atl":      (md.get("atl") or {}).get("usd"),
            "ath_date": _date((md.get("ath_date") or {}).get("usd")),
            "atl_date": _date((md.get("atl_date") or {}).get("usd")),
        }
    except Exception as exc:  # noqa: BLE001
        print(f"[cg_market] Warning: could not fetch ATH/ATL for {sym} ({cg_id}): {exc}")
        result = {**_EMPTY}

    _mem_cache[sym] = result
    _save_disk(sym, result)
    return result
