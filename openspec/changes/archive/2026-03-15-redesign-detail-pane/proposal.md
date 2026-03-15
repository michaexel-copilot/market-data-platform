## Why

The current detail pane uses a horizontal tab-bar that forces the user to switch between four separate views (Chart & Trades, Performance, Fundamentals, Place Order), hiding all context except the active tab. An accordion layout keeps all sections visible and accessible on one scrollable page, letting the user expand only what they need without losing their place.

## What Changes

- Replace the four-tab button-group navigation with a Bootstrap accordion (six panels).
- Each accordion panel renders its content inline; no full-pane HTMX reload is needed to switch sections.
- Default expanded panels: Fundamentals (1st), Strategy Controls (3rd).
- Default collapsed panels: Chart (2nd), Trades Table (4th), Performance (5th), Place Order (6th).
- Hidden inputs that preserved state across tab-reloads are consolidated — state is now carried by the accordion structure itself, not by separate tab switches.
- The tab-input hidden field and tab-switch HTMX calls are removed.

### Panel mapping

| # | Accordion header | Contents | Default |
|---|---|---|---|
| 1 | Fundamentals | Market Cap, ATH/ATL cards, OHLC Source, Chain/Platform | expanded |
| 2 | Chart | Candlestick chart image | collapsed |
| 3 | Strategy Controls | SMA/SL spinners, Position size, Find Best SMA button, Short/Long strategy summaries | expanded |
| 4 | Trades | Unified short+long trade table | collapsed |
| 5 | Performance | Stats table + lightweight-charts interactive chart | collapsed |
| 6 | Place Order | Full order form (margin, side, leverage, size, TP/SL) | collapsed |

## Capabilities

### New Capabilities

- `detail-pane-accordion`: Single-page accordion view that replaces the tab-based navigation in `asset_detail.html`. Covers panel structure, default open/closed state, and scroll behaviour.

### Modified Capabilities

_(none — no existing spec-level requirements are changing)_

## Impact

- **`templates/asset_detail.html`** — primary change: remove tab selector + `{% if tab == ... %}` branches; add Bootstrap accordion markup with six `.accordion-item` panels.
- **`web.py`** — minor: the `tab` query-parameter handling and the four separate tab branches in the `/asset/{symbol}` route become unnecessary; the route can return a single unified partial. Hidden inputs for state preservation are still needed for HTMX-triggered field changes (SMA spinners, etc.).
- **No backend logic changes** — all data already flows through the single `GET /asset/{symbol}` handler; the accordion just changes how it is rendered.
- **No new dependencies** — Bootstrap accordion is already available via the existing Bootstrap 5 import.
