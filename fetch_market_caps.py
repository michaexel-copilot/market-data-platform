import csv
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent
cmc_key = os.environ.get("CMC_API_KEY", "")
if not cmc_key:
    print("No CMC_API_KEY set — market caps will be empty for all symbols.")

INPUT_CSV = ROOT / "hl_testnet_pairs.csv"
OUTPUT_CSV = ROOT / "hl_testnet_pairs_with_mcap.csv"
CMC_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"

# Hyperliquid uses "K" prefix for kilo-unit tokens (e.g. KPEPE = 1000 PEPE).
# Map those back to their real CMC symbol.
# Also handle rebranded tokens.
K_PREFIX_MAP = {
    # Kilo-unit tokens
    "KBONK": "BONK",
    "KDOGS": "DOGS",
    "KFLOKI": "FLOKI",
    "KLUNC": "LUNC",
    "KNEIRO": "NEIRO",
    "KPEPE": "PEPE",
    "KSHIB": "SHIB",
    # Rebranded tokens
    "FTM": "S",          # Fantom → Sonic
    "MATIC": "POL",      # Polygon → POL
    "RNDR": "RENDER",    # Render (old ticker)
    "NEIROETH": "NEIRO", # Neiro on ETH
    "FXS": "FXS",        # Frax Share (keep, try as-is first)
}

def read_pairs(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def fetch_quotes(symbols):
    """Fetch USD market cap for a list of symbols from CMC (max 100 per call)."""
    headers = {"X-CMC_PRO_API_KEY": cmc_key, "Accept": "application/json"}
    params = {"symbol": ",".join(symbols), "convert": "USD"}
    resp = requests.get(CMC_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", {})

def main():
    rows = read_pairs(INPUT_CSV)

    # Build list of unique CMC symbols and remember the mapping
    hl_to_cmc = {}   # HL base symbol -> CMC symbol
    cmc_symbols = set()
    for row in rows:
        base = row["base"]
        cmc_sym = K_PREFIX_MAP.get(base, base)
        hl_to_cmc[base] = cmc_sym
        cmc_symbols.add(cmc_sym)

    # Fetch in batches of 100
    mcap_map = {}   # CMC symbol -> market_cap (USD)
    for batch in chunks(sorted(cmc_symbols), 100):
        print(f"Fetching {len(batch)} symbols: {batch[:5]}...")
        data = fetch_quotes(batch)
        for sym, info in data.items():
            # CMC may return multiple entries when symbol is ambiguous;
            # pick the one with the highest market cap (most prominent coin).
            entries = info if isinstance(info, list) else [info]
            best = max(entries, key=lambda e: (e.get("quote", {}).get("USD", {}).get("market_cap") or 0))
            mcap = best.get("quote", {}).get("USD", {}).get("market_cap")
            mcap_map[sym.upper()] = mcap
        time.sleep(0.5)  # be polite to the API

    # Attach market cap to each row
    for row in rows:
        base = row["base"]
        cmc_sym = hl_to_cmc[base]
        row["cmc_symbol"] = cmc_sym
        mc = mcap_map.get(cmc_sym.upper(), "")
        row["market_cap_usd"] = mc

    # Sort by market_cap_usd descending (rows without data go to the bottom)
    rows.sort(
        key=lambda r: float(r["market_cap_usd"]) if r["market_cap_usd"] else -1,
        reverse=True,
    )

    # Write output
    fieldnames = list(rows[0].keys())
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Output written to {OUTPUT_CSV}")
    found = sum(1 for r in rows if r["market_cap_usd"])
    print(f"Market cap found for {found}/{len(rows)} symbols.")
    print("Top 5 by market cap:")
    for r in rows[:5]:
        mc = float(r['market_cap_usd'])
        print(f"  {r['symbol']:<30} ${mc:>20,.0f}")

if __name__ == "__main__":
    main()
