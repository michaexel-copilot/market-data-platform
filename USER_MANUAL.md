# Short Opportunities — User Manual

A web application for identifying and trading short opportunities on Hyperliquid perpetuals.

---

## Table of Contents

1. [Interface Overview](#1-interface-overview)
2. [Sidebar — Asset List](#2-sidebar--asset-list)
3. [Fundamentals Panel](#3-fundamentals-panel)
4. [Chart Panel](#4-chart-panel)
5. [Strategy Controls Panel](#5-strategy-controls-panel)
6. [Trades Panel](#6-trades-panel)
7. [Performance Panel](#7-performance-panel)
8. [Place Order Panel](#8-place-order-panel)
9. [Data Sources](#9-data-sources)
10. [Keyboard Reference](#10-keyboard-reference)
11. [Known Limitations](#11-known-limitations)

---

## 1. Interface Overview

Open the application at `http://localhost:8000`.

The screen is divided into two panes:

- **Left — Sidebar**: the asset list with filter, Favourites and Ignored panels, and the Testnet/Mainnet network toggle.
- **Right — Detail pane**: charts, stats, and order forms for the selected asset, organised as a **vertical accordion**. Each section can be expanded or collapsed independently by clicking its header.

Click any asset in the sidebar to load its detail view. The **Fundamentals** and **Strategy Controls** panels open automatically; the rest start collapsed.

---

## 2. Sidebar — Asset List

### Network Toggle

At the very top of the sidebar is a **Testnet / Mainnet** toggle.

| Option | Behaviour |
|--------|-----------|
| **Testnet** (default) | Loads the Hyperliquid testnet asset list. Safe for practice trading. |
| **Mainnet** | Loads the full Hyperliquid mainnet asset list. Switches the Place Order tab to real-money mode (red border). |

Switching the toggle immediately reloads the asset list. Your Favourites and Ignored state is preserved across switches.

### Asset Item Display

Each asset in the list shows:

- **Rank** — CoinMarketCap market-cap rank (`#1`, `#2`, …)
- **Symbol** — trading symbol (e.g. `BTC`, `SOL`)
- **Market cap** — in $B (billions), shown in grey below the symbol
- **Launch date** — date the token was launched, if available

### Three Panels

The sidebar has three resizable panels separated by draggable dividers:

| Panel | Default Size | Purpose |
|-------|-------------|---------|
| **Main** | 30% | All assets, sorted by market cap descending |
| **Favourites** | 60% | Assets you have starred |
| **Ignored** | 10% | Assets you have hidden from the Main list |

**Resizing panels**: Drag the horizontal divider bar between panels up or down. Heights are saved to `localStorage` and restored on reload.

### Filter

The search box at the top of the sidebar filters the Main list in real time by symbol. Press **Escape** to clear the filter and return focus to the filter input.

### Managing Assets

| Action | How |
|--------|-----|
| Add to Favourites | Click the ★ button on the asset row, or press **F** while the asset is focused |
| Remove from Favourites | Click the ★ button again in the Favourites panel |
| Ignore (hide) an asset | Click the ✕ button on the asset row, or press **I** while the asset is focused |
| Restore an ignored asset | Click the asset name in the Ignored panel (or the ↩ button) |

The selection focus automatically moves to the next visible asset when you ignore the currently selected one.

### Badge Counter

The asset count badge next to "Assets" shows the total number of items in the current network's list. When a filter is active it shows `visible / total`.

---

## 3. Fundamentals Panel

Shows metadata for the selected asset assembled from CoinMarketCap and CoinGecko.

| Field | Source | Description |
|-------|--------|-------------|
| **Market Cap** | CoinMarketCap | Total market capitalisation in USD |
| **Launched** | CoinMarketCap | Token launch date (YYYY-MM-DD) |
| **ATH** | CoinGecko | All-time high price, the date it occurred, and % difference vs current price |
| **ATL** | CoinGecko | All-time low price, the date it occurred, and % difference vs current price |
| **OHLC Source** | Internal | Whether OHLCV data is fetched from EODHD, Yahoo Finance, or CoinGecko |
| **Chain / Platform** | CoinMarketCap | Blockchain or platform the token lives on, with contract address if available |

The asset name at the top is a clickable link to the CoinMarketCap page (when available).

---

## 4. Chart Panel

### Chart

The main chart shows **12 months of daily OHLC data** as a price line (close price) with three SMA overlays:

| Line | Colour | Meaning |
|------|--------|---------|
| Close | Black | Daily closing price |
| SMA High | Light blue | Simple moving average of daily **highs** |
| SMA Low | Green | Simple moving average of daily **lows** — the **strategy signal line** |
| SMA Close | Purple | Simple moving average of daily closes |

When a trade is highlighted (see Highlighting below):
- **Short trade**: blue crosshairs (dashed) mark the entry and orange crosshairs (dashed) mark the exit
- **Long trade**: green crosshairs (dotted) mark the entry and red crosshairs (dotted) mark the exit

Both highlights can be active simultaneously — switching between panels does not clear the other strategy's crosshairs.

### SMA Period LOW and SL Short % (left column)

The left column contains two controls for the **Short Strategy**:

**SMA Period LOW** — controls the lookback window for the SMA Low and SMA Close signal lines.

- **Default**: 7 days
- **Range**: 1 – 500 days
- Change by typing a number in the spinner, or using keyboard shortcuts (see [Keyboard Reference](#8-keyboard-reference))
- The chart and trade table reload automatically when the value changes

**SL Short %** — sets the stop-loss percentage for the Short Strategy.

- **Default**: 10%
- **Range**: 1% – 50%
- A value of 10 means the short exits at a loss when the price rises 10% above the entry price

### SMA Period HIGH and SL Long % (right column)

The right column contains two controls for the **Long Strategy**:

**SMA Period HIGH** — controls the lookback window for the SMA High signal line.

- **Default**: 7 days
- **Range**: 1 – 500 days
- Same keyboard shortcuts as SMA Period LOW (spinner must be focused)
- Changes reload the chart automatically

**SL Long %** — sets the stop-loss percentage for the Long Strategy.

- **Default**: 10%
- **Range**: 1% – 50%
- A value of 10 means the long exits at a loss when the price falls 10% below the entry price

### Find Best SMA

The **Find Best SMA** button searches all SMA LOW × SMA HIGH period combinations in the range 3–50 and selects the pair that maximises the combined average P&L per closed trade across both strategies.

- **Auto-runs** when you select a ticker — no manual click needed
- Results are **cached** per symbol for the current day; repeated clicks use the cached result instantly
- After the calculation completes, **the SMA Period LOW and SMA Period HIGH spinners are updated** to the winning values and the chart reloads automatically
- You can also click the button manually at any time (e.g. after changing SL %)
- A spinner indicator is shown on the button while the calculation runs (may take a few seconds)

### Position Size

Sets the hypothetical USD position size used to calculate P&L in the trade table.

- **Default**: $100
- **Minimum**: $100, in steps of $100
- Changing the value reloads the trade table

---

## 5. Strategy Controls Panel

This panel (expanded by default) contains the SMA period spinners, stop-loss inputs, Position Size, the **Find Best SMA** button, and the short/long strategy summaries described in [Chart Panel](#4-chart-panel) above.

---

## 6. Trades Panel

Shows all short and long trades from the last 12 months in the unified trade table described in [Chart Panel](#4-chart-panel) above. Collapsed by default; click the header to expand.

---

### Short Strategy — How It Works

The strategy backtests a simple short-selling rule on the last 12 months of daily data:

**Entry**: The daily close crosses **below** the SMA-Low line (it was ≥ SMA-Low yesterday and < SMA-Low today). A short position is opened at the closing price.

**Exit — Stop Loss**: If the close rises to ≥ `(1 + SL Short % / 100)` × entry price, the position exits at that level (a loss).

**Exit — Take Profit**: If the SMA-Low falls below the entry price and the current close is ≥ the current SMA-Low, the position exits at the current SMA-Low value (a profit).

Only one position can be open at a time. Each new entry waits for the previous position to close.

P&L is calculated as: `(entry_price − exit_price) / entry_price × position_size_usd`

### Long Strategy — How It Works

The strategy backtests a simple long-buying rule on the last 12 months of daily data:

**Entry**: The daily close crosses **above** the SMA-High line (it was ≤ SMA-High yesterday and > SMA-High today). A long position is opened at the closing price.

**Exit — Stop Loss**: If the close falls to ≤ `(1 − SL Long % / 100)` × entry price, the position exits at that level (a loss).

**Exit — Take Profit**: If the SMA-High rises above the entry price and the current close is ≥ the current SMA-High, the position exits at the current SMA-High value (a profit).

Only one position can be open at a time.

P&L is calculated as: `(exit_price − entry_price) / entry_price × position_size_usd`

### Trade Table

All short and long trades from the last 12 months are shown in a **single unified table**, sorted by entry date descending (most recent first). Each row is colour-coded by direction:

| Row colour | Direction |
|------------|-----------|
| Light red (`#ffe8e8`) | Short trade |
| Light green (`#e8f5e8`) | Long trade |

*Note: the P&L and Max Δ P&L columns retain only their text colour (green/red) and are not given the row background colour.*

| Column | Description |
|--------|------------|
| **Dir** | ▼ Short or ▲ Long |
| **#** | Signal number |
| **Entry Date** | Date the position was entered |
| **Entry $** | Price at entry (4 significant figures) |
| **Exit Date** | Date the position closed (`—` if still open) |
| **Exit $** | Price at exit (`—` if still open) |
| **P&L** | Realised profit/loss in USD. Open positions show a live estimate prefixed with `~`. Green = profit, Red = loss, Blue = open |
| **Max Δ P&L** | The worst unrealised P&L seen while the trade was open — see below |

**Max Δ P&L details:**

*Short strategy*: For **profit trades**: the maximum adverse excursion (how deep in the red the position went before turning profitable) — shown in red; ✓ (green) means the trade was never underwater. For **loss trades**: the maximum favourable excursion (the best unrealised gain before the stop-loss was hit) — shown in green; `—` means the trade was never profitable.

*Long strategy*: Mirrored — adverse means price fell (shown in red), favourable means price rose (shown in green).

Open trades show `—` in Max Δ P&L.

**Strategy summaries** (above the table, always visible) show two compact blocks — one for Short, one for Long — each displaying:
- **Trade count** — number of closed trades
- **Total P&L** — sum of all closed-trade P&L (green = positive, red = negative)
- **Avg P&L/trade** — Total P&L ÷ trade count

**Highlighting a trade**: Click any row to redraw the chart with crosshairs at that trade's entry and exit. Short trades use blue (entry) and orange (exit) dashed crosshairs; long trades use green (entry) and red (exit) dotted crosshairs. Both strategies' highlights persist independently.

If no signals were found in the last 12 months, a message is displayed instead of a table.

---

## 7. Performance Panel

Shows recent price statistics and an interactive candlestick chart. Collapsed by default.

### Stats Table

| Column | Description |
|--------|------------|
| **Period** | Time window: 1D, 7D, 30D, 1Y, 5Y |
| **High** | Highest price reached in the period |
| **Low** | Lowest price reached in the period |
| **VWAP** | Volume-weighted average price `(sum of typical_price × volume) / total_volume` |
| **Volume** | Total traded USD volume in the period |
| **Chart lines** | Colour-coded legend for the H/L reference lines on the chart |

Prices are shown in **USD** and **EUR** (EUR values appear below in blue, based on today's exchange rate).

Periods older than the available data are suppressed (shown as `—`).

### Legend (right of table)

Explains the chart line styles:

- **Dashed line** = period High
- **Dotted line** = period Low
- Colours: blue = 1D, orange = 7D, green = 30D

### Interactive Chart

An interactive price chart using **~90 days** of data at the selected resolution:

- **Resolution toggle**: **1H** or **4H** (default 4H) bars. Switch using the buttons above the chart within this panel.
- **Visible window**: the last **35 days** are shown by default on the x-axis
- **Y-axis**: pinned so the **30D high sits at the 95% mark** and the **30D low sits at the 5% mark**, giving context to where the current price sits within the 30-day range
- **Reference lines**: 30D, 7D, and 1D high (dashed) and low (dotted) are drawn as horizontal lines spanning their respective window
- **Candlestick mode**: available when data comes from EODHD or Yahoo Finance (full OHLCV with real H/L). CoinGecko-sourced assets show a line chart instead (close-only data)
- The chart is interactive — hover to see exact values on the crosshair. Pan and zoom with the mouse wheel or by dragging

---

## 8. Place Order Panel

Places perpetual futures orders on Hyperliquid directly from the app. Collapsed by default.

> ⚠️ **Warning**: When the sidebar is set to **Mainnet**, this form places real orders with real money. The order card is outlined in **red** as a reminder.

### Network

The network (Testnet or Mainnet) is controlled by the toggle at the **top of the sidebar**, not within this form. Switch to Testnet for practice orders; switch to Mainnet only when you intend to trade with real funds.

### Form Fields

| Field | Default | Options / Range | Notes |
|-------|---------|-----------------|-------|
| **Margin** | Cross | Cross, Isolated | Cross margin shares your full account balance as collateral |
| **Position** | Sell / Short | Sell / Short, Buy / Long | Changing side resets the leverage and swaps the TP/SL defaults |
| **Leverage** | 2× (Short), 1× (Long) | 1× – max× (slider) | Maximum depends on the asset; shown at the right end of the slider |
| **Order Type** | Market | Market, Limit | Limit reveals the Limit Price field |
| **Limit Price** | Last close | Any positive number | Only visible when Limit is selected |
| **Size (USD)** | — | ≥ $10 | Required. Enter the notional USD value of the position |

### Risk Management

Choose one mode:

**Take Profit & Stop Loss** (default)

| Sub-field | Default | Description |
|-----------|---------|-------------|
| Take Profit ($) | 30D Low (for Short) / 30D High (for Long) | Target exit price. The % gain is calculated and shown automatically. |
| Stop Loss ($) | 30D High (for Short) / 30D Low (for Long) | Maximum loss exit price. The % loss is calculated and shown automatically. |

When leverage > 1×, the **levered gain** and **levered loss** percentages are shown below the TP/SL fields — these reflect the actual return on your margin, not the notional position.

**Reduce Only** — Places a position-closing order only (no TP/SL).

### Placing an Order

1. Fill in all fields and click **Place Order**
2. A confirmation dialog appears summarising all parameters
3. Review carefully — the Network (Testnet / ⚠️ MAINNET), symbol, side, leverage, size, TP, and SL are all shown
4. Click **Confirm & Place** to send the order, or **Cancel** to go back
5. On success, the order ID (and TP/SL order IDs if applicable) are displayed

---

## 9. Data Sources

### OHLCV Price Data

Price data is fetched automatically and cached to disk for the current day.

| Source | Used when |
|--------|-----------|
| **EODHD** (local service) | Primary source for supported assets (currently BTC, ETH, ADA, ALGO, SKY). Provides true hourly OHLCV data from Oct 2020 with real high/low ranges. No external API calls — served by a local service at `http://localhost:8010`. |
| **Yahoo Finance** | Default for assets not covered by EODHD. Provides full daily OHLCV (open, high, low, close, volume) from 2020-01-01. |
| **CoinGecko** | For assets not listed on Yahoo Finance and not covered by EODHD (e.g. HYPE, SUI, MNT). Provides close-only daily data; the Performance chart shows a line chart. |

EODHD hourly candles are resampled to daily candles before use in charts and backtesting, so the interface remains consistent across all sources. The 4H and 1H resolution in the Performance tab uses native EODHD hourly data for covered symbols.

**K-prefix tokens** (KBONK, KPEPE, KSHIB, etc.) represent 1000 × the underlying coin. Prices are fetched from the underlying token and multiplied by 1000 automatically.

The **OHLC Source** is shown in the Fundamentals panel.

### EUR / USD Exchange Rate

Performance tab prices are converted to EUR using an exchange rate fetched once per day from `open.er-api.com`. The rate is cached and reused for the rest of the day.

---

## 10. Keyboard Reference

### Sidebar

| Key | Action |
|-----|--------|
| `↑` / `↓` | Move selection up / down through the visible Main list |
| `Enter` (on an asset) | Load the asset's detail view |
| `F` (on a focused asset) | Toggle Favourite |
| `I` (on a focused asset) | Ignore (hide) the asset |
| `Escape` | Clear the filter box and focus it |
| `↓` (from filter box) | Move focus to the first visible asset |

### SMA Period LOW / HIGH and SL Short % / SL Long % Spinners (Strategy Controls panel, spinner must be focused)

| Key | Change |
|-----|--------|
| `+` / `=` | +1 |
| `-` | −1 |
| `Shift` + `+` / `-` | ±5 |
| `Ctrl` + `Shift` + `+` / `-` | ±10 |

Shortcuts apply independently to whichever spinner is focused. The same key bindings work for all four spinners.

---

## 11. Known Limitations

- **Market orders**: Executed at the current best bid/ask. Actual fill price may differ from the displayed last close, especially in thin markets.
- **CoinGecko OHLC**: The Performance chart shows a line (close-only) for CoinGecko-sourced assets. High/Low values in the stats table reflect CoinGecko's daily OHLC candles, which use a different aggregation method than exchange data.
- **Assets with no price data**: If neither EODHD, Yahoo Finance, nor CoinGecko has data for an asset, a warning is shown in place of the chart. The Performance and Place Order panels still function using other data sources.
- **Exchange rate**: The USD→EUR rate is refreshed once per day. Prices shown in EUR during the session reflect the rate at the time of the last refresh.
- **Mainnet orders are irreversible**: Once confirmed, orders are sent directly to the Hyperliquid exchange. Always review the confirmation dialog before clicking Confirm.
- **Testnet asset list**: The testnet list contains a subset of assets compared to mainnet. Not all mainnet assets are available for testnet trading.
