"""
web: FastAPI + HTMX two-pane chart viewer.

Start with:   uv run serve
Then open:    http://localhost:8000
"""
import csv
import sys
from datetime import date
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from cmc_info import fetch_cmc_info          # noqa: E402
from draw_chart import draw_chart, get_data_source  # noqa: E402

CSV_PATH  = ROOT / "hl_testnet_pairs_with_mcap.csv"
PNG_DIR   = ROOT / "png"
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))

app = FastAPI(title="Short Opportunities")
app.mount("/png", StaticFiles(directory=str(PNG_DIR)), name="png")

# ---------------------------------------------------------------------------
# Asset list — loaded once at startup
# ---------------------------------------------------------------------------

def _load_assets() -> list[dict[str, Any]]:
    with open(CSV_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    assets = []
    for rank, row in enumerate(rows, start=1):
        mc = row.get("market_cap_usd", "")
        assets.append({
            "rank":          rank,
            "symbol":        row["base"],
            "cmc_symbol":    row.get("cmc_symbol", row["base"]),
            "market_cap_usd": float(mc) if mc else None,
        })
    return assets


ASSETS: list[dict[str, Any]] = _load_assets()
ASSET_BY_SYMBOL: dict[str, dict[str, Any]] = {a["symbol"]: a for a in ASSETS}


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _today_prefix(symbol: str, sma_period: int) -> str:
    """Return the filename prefix used for today's chart, e.g. SOLUSD_2026-02-24_SMA44"""
    return f"{symbol.upper()}USD_{date.today()}_SMA{sma_period}"


def _find_existing_chart(symbol: str, sma_period: int) -> str | None:
    """Return the filename (not path) of the newest chart for today, or None."""
    prefix = _today_prefix(symbol, sma_period)
    PNG_DIR.mkdir(exist_ok=True)
    matches = sorted(PNG_DIR.glob(f"{prefix}_*.png"), reverse=True)
    return matches[0].name if matches else None


def _get_or_create_chart(symbol: str, sma_period: int) -> str | None:
    """Return the filename for today's chart, generating it if needed."""
    existing = _find_existing_chart(symbol, sma_period)
    if existing:
        return existing
    try:
        path = draw_chart(symbol, sma_period=sma_period)
        return path.name
    except Exception as exc:  # noqa: BLE001
        print(f"[web] Could not generate chart for {symbol}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        "index.html",
        {"request": request, "assets": ASSETS},
    )


@app.get("/asset/{symbol}", response_class=HTMLResponse)
async def asset_detail(request: Request, symbol: str, sma: int = 44) -> HTMLResponse:
    sym_upper = symbol.upper()
    asset = ASSET_BY_SYMBOL.get(sym_upper)

    cmc_symbol = asset["cmc_symbol"] if asset else sym_upper

    info = fetch_cmc_info(cmc_symbol)
    chart_filename = _get_or_create_chart(sym_upper, sma_period=sma)

    return TEMPLATES.TemplateResponse(
        "asset_detail.html",
        {
            "request":        request,
            "symbol":         sym_upper,
            "market_cap_usd": asset["market_cap_usd"] if asset else None,
            "info":           info,
            "chart_filename": chart_filename,
            "data_source":    get_data_source(sym_upper),
            "sma_period":     sma,
        },
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    uvicorn.run("web:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
