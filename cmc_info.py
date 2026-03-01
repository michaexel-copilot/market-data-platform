"""
cmc_info: fetch fundamental data from CoinMarketCap /v2/cryptocurrency/info.

Returned dict keys:
  name          str        — full coin name
  date_launched str | None — ISO date the chain/token actually launched
                             e.g. "2009-01-03T00:00:00.000Z" for Bitcoin
                             Falls back to date_added (CMC listing date) when absent.
  platform      str | None — chain name if token, e.g. "Ethereum", "Solana"
  token_address str | None — contract address on the platform chain
"""
import json
import sys
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from coinMarketCapKey import cmc_key  # noqa: E402

CMC_INFO_URL = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/info"

CACHE_DIR = ROOT / "cache" / "cmc_info"

# In-process cache (reset on server restart — backed by disk below)
_cache: dict[str, dict] = {}


def _cache_path(sym: str) -> Path:
    return CACHE_DIR / f"{sym}_{date.today()}.json"


def _load_disk_cache(sym: str) -> dict | None:
    path = _cache_path(sym)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return None


def _save_disk_cache(sym: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(sym).write_text(json.dumps(data))


def fetch_cmc_info(cmc_symbol: str) -> dict:
    """
    Return a dict with name, date_launched, platform, token_address for the
    given CMC symbol.  On any error returns a dict with None values so callers
    don't need to deal with exceptions.
    """
    sym = cmc_symbol.upper()
    if sym in _cache:
        return _cache[sym]

    # Check disk cache before hitting the network
    disk = _load_disk_cache(sym)
    if disk is not None:
        _cache[sym] = disk
        return disk

    empty = {"name": sym, "date_launched": None, "platform": None, "token_address": None}
    try:
        headers = {"X-CMC_PRO_API_KEY": cmc_key, "Accept": "application/json"}
        params = {"symbol": sym}
        resp = requests.get(CMC_INFO_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        # data is a dict keyed by symbol; each value is a list of entries
        entries = data.get(sym, [])
        if not entries:
            _cache[sym] = empty
            return empty

        # When multiple coins share the same symbol, pick the one with the
        # lowest CMC id — that is always the original / most prominent listing.
        entry = entries[0] if len(entries) == 1 else min(
            entries,
            key=lambda e: (e.get("id") or 999_999_999),
        )

        # Prefer date_launched (actual blockchain/token launch date) over
        # date_added (when the coin was listed on CoinMarketCap).
        date_launched = entry.get("date_launched") or entry.get("date_added")

        platform = entry.get("platform")
        result = {
            "name":          entry.get("name", sym),
            "date_launched": date_launched,
            "platform":      platform.get("name") if platform else None,
            "token_address": platform.get("token_address") if platform else None,
        }
        _cache[sym] = result
        _save_disk_cache(sym, result)
        return result

    except Exception as exc:  # noqa: BLE001
        print(f"[cmc_info] Warning: could not fetch info for {sym}: {exc}")
        _cache[sym] = empty
        return empty


# ---------------------------------------------------------------------------
# K-scale symbol mapping (HL uses KBONK etc. for 1000× contracts)
# ---------------------------------------------------------------------------
_K_SCALE: set[str] = {"KBONK", "KDOGS", "KFLOKI", "KLUNC", "KNEIRO", "KPEPE", "KSHIB"}


def _to_cmc_sym(hl_sym: str) -> str:
    """Map a Hyperliquid symbol to its CoinMarketCap equivalent."""
    s = hl_sym.upper()
    return s[1:] if s in _K_SCALE else s


# ---------------------------------------------------------------------------
# Batch market-cap fetch
# ---------------------------------------------------------------------------

CMC_QUOTES_URL = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"


def fetch_market_caps(hl_symbols: list[str]) -> dict[str, float | None]:
    """
    Batch-fetch market caps for a list of HL symbols.
    Returns {hl_symbol: market_cap_usd | None}.
    """
    result: dict[str, float | None] = {s: None for s in hl_symbols}

    # Build CMC-symbol → [hl_symbols] mapping
    cmc_to_hl: dict[str, list[str]] = {}
    for hl in hl_symbols:
        cs = _to_cmc_sym(hl)
        cmc_to_hl.setdefault(cs, []).append(hl)

    headers = {"X-CMC_PRO_API_KEY": cmc_key, "Accept": "application/json"}
    cmc_syms = list(cmc_to_hl.keys())

    for i in range(0, len(cmc_syms), 100):
        batch = cmc_syms[i : i + 100]
        try:
            resp = requests.get(
                CMC_QUOTES_URL,
                headers=headers,
                params={"symbol": ",".join(batch)},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            for cs, entries in data.items():
                if not entries:
                    continue
                entry = (
                    min(entries, key=lambda e: e.get("id") or 999_999_999)
                    if len(entries) > 1
                    else entries[0]
                )
                mc = (entry.get("quote") or {}).get("USD", {}).get("market_cap")
                for hl in cmc_to_hl.get(cs.upper(), cmc_to_hl.get(cs, [])):
                    result[hl] = mc
        except Exception as exc:  # noqa: BLE001
            print(f"[cmc_info] Warning: market-cap batch fetch failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# Batch CMC info fetch (date_launched etc.)
# ---------------------------------------------------------------------------


def fetch_cmc_info_batch(hl_symbols: list[str]) -> dict[str, dict]:
    """
    Fetch CMC info (name, date_launched, platform, …) for many HL symbols.
    Reads per-symbol disk caches first; only calls the API for uncached ones.
    Returns {hl_symbol: info_dict}.
    """
    result: dict[str, dict] = {}
    need_fetch: list[str] = []

    for hl in hl_symbols:
        cs = _to_cmc_sym(hl).upper()
        if cs in _cache:
            result[hl] = _cache[cs]
        else:
            disk = _load_disk_cache(cs)
            if disk is not None:
                _cache[cs] = disk
                result[hl] = disk
            else:
                need_fetch.append(hl)

    if not need_fetch:
        return result

    cmc_to_hl: dict[str, list[str]] = {}
    for hl in need_fetch:
        cs = _to_cmc_sym(hl).upper()
        cmc_to_hl.setdefault(cs, []).append(hl)

    def _empty(sym: str) -> dict:
        return {"name": sym, "date_launched": None, "platform": None, "token_address": None}

    headers = {"X-CMC_PRO_API_KEY": cmc_key, "Accept": "application/json"}
    cmc_syms = list(cmc_to_hl.keys())

    for i in range(0, len(cmc_syms), 100):
        batch = cmc_syms[i : i + 100]
        try:
            resp = requests.get(
                CMC_INFO_URL,
                headers=headers,
                params={"symbol": ",".join(batch)},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            for cs in batch:
                entries = data.get(cs, [])
                if not entries:
                    info = _empty(cs)
                else:
                    entry = (
                        min(entries, key=lambda e: e.get("id") or 999_999_999)
                        if len(entries) > 1
                        else entries[0]
                    )
                    dl = entry.get("date_launched") or entry.get("date_added")
                    platform = entry.get("platform")
                    info = {
                        "name":          entry.get("name", cs),
                        "date_launched": dl,
                        "platform":      platform.get("name") if platform else None,
                        "token_address": platform.get("token_address") if platform else None,
                    }
                _cache[cs] = info
                _save_disk_cache(cs, info)
                for hl in cmc_to_hl.get(cs, []):
                    result[hl] = info
        except Exception as exc:  # noqa: BLE001
            print(f"[cmc_info] Warning: info batch fetch failed for batch {i//100}: {exc}")
            for cs in batch:
                for hl in cmc_to_hl.get(cs, []):
                    result.setdefault(hl, _empty(cs))

    # Fill any symbols that slipped through
    for hl in need_fetch:
        if hl not in result:
            result[hl] = _empty(_to_cmc_sym(hl).upper())

    return result
