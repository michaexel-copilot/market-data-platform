# Plan: Draw Daily OHLC Chart with SMAs

Implement a new script `draw_chart.py` that fetches 12 months of daily OHLC data from CoinMarketCap for a given symbol, draws a price chart with three SMA-44 overlays, and saves a 3000×2000 PNG to `png/`.

## Steps

1. **Add dependencies** in `pyproject.toml`: add `matplotlib` (for rendering) to the `dependencies` list. Run `uv add matplotlib` to lock it.

2. **Create `draw_chart.py`** with a `main()` entry point that:
   - Accepts a single CLI positional argument: the symbol (e.g. `SOL`)
   - Resolves the CMC symbol using the same K-prefix / rename logic already present in `fetch_market_caps.py` (extract shared mapping or duplicate it)
   - Calls CMC `/v1/cryptocurrency/ohlcv/historical` with `time_period=daily`, `count=365`, `symbol=<cmc_symbol>` using the key from `coinMarketCapKey.py`
   - For K-prefixed symbols multiplies every OHLC price value by 1000

3. **Compute SMA-44** three times over the returned daily series:
   - Over the `high` series → `sma_high` (#99ccff)
   - Over the `low` series → `sma_low` (#327819)
   - Over the `close` series → `sma_close` (#bd44bd)

4. **Render the chart** with `matplotlib` at 3000×2000 px (set `figsize=(30, 20)` at 100 dpi):
   - Main line: daily `close` price, color black, linewidth 1
   - Three SMA lines at linewidth 1 with the specified colors
   - X-axis: daily resolution, tick marks at the 1st of each month, labels as `MMM YYYY` (e.g. `Feb 2025`)
   - Y-axis: tight to `[min(low), max(high)]` across the 365 days, no extra padding
   - Legend identifying SMA44-High, SMA44-Low, SMA44-Close by color
   - Title: the symbol string passed in

5. **Save output** to `png/{SYMBOL}USD_{YYYY-MM-DD}_{HH-MM-SS}.png`, matching the naming convention of the existing files in `png/`.

6. **Register the entrypoint** in `pyproject.toml`:
   ```
   draw-chart = "draw_chart:main"
   ```
   So the script runs via `uv run draw-chart SOL`.

## Verification

- Run `uv run draw-chart SOL` — confirm a PNG appears in `png/` with today's timestamp
- Open the PNG and visually verify: 3000×2000, black close-price line, three colored SMA-44 lines, monthly X-axis labels, legend present
- Run with a K-prefix symbol (e.g. `uv run draw-chart KSHIB`) and confirm prices are scaled ×1000 vs. raw SHIB CMC price

## Decisions

- CLI arg over CSV batch: allows targeted single-coin charts on demand
- "closing price" main line: confirmed (typo in spec)
- K-prefix symbols: prices scaled ×1000 to match HL contract unit
- Output to `png/` with `SYMBOL_DATE_TIME.png` naming: consistent with existing files
