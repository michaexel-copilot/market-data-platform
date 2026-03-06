# Plan: "Place Order" Tab — f16

Add a 4th **"Place Order"** tab to the asset detail view. A Bootstrap form sends parameters to a new `POST /asset/{symbol}/order` FastAPI endpoint, which uses the existing `hl_client` library to place orders on Hyperliquid testnet (default) or mainnet.

---

## Phase 1 — Backend Scaffolding

**Step 1: `pyproject.toml` — two new deps**
- `hl-client @ file:///work/projekte/hyperliquid-python/hl_client` (the local SDK)
- `python-dotenv>=1.0` (to load credentials from `.env`)

**Step 2: `.env` in project root**
- Copy the four keys from `hl_client/.env.example`: `HL_MASTER_PRIVATE_KEY`, `HL_MASTER_WALLET_ADDRESS`, `HL_TEST_PRIVATE_KEY`, `HL_TEST_WALLET_ADDRESS`
- Add `.env` to `.gitignore`

**Step 3: Create `hl_order.py`**
- Loads `.env` on import
- Reads pairs metadata (lot_size, max_leverage, HL symbol string e.g. `BTC/USDC:USDC`) from testnet CSV and the mounted mainnet CSV — loaded once at module level
- `async place_order(symbol, side, order_type, size_usd, leverage, margin_type, reduce_only, tp_price, sl_price, testnet)`:
  1. `_exchange.set_leverage(leverage, symbol)` via `client._exchange`
  2. Calls `client.place_market_order()` or `client.place_limit_order()`
  3. If TP/SL mode: after fill, places two additional reduce-only orders — TP as a limit order, SL as a stop-market — via `client._exchange.create_order(params={'reduceOnly': True, ...})`
  4. Size→amount conversion: `amount = round(size_usd / last_price, lot_size_decimals)`

**Step 4: Extend `GET /asset/{symbol}` route in `web.py`**
- When `tab == "order"`: fetch `fetch_5y_candles()` → `compute_perf_rows()` → extract `30D` row for default TP/SL values
- Look up `max_leverage` and `lot_size` for the symbol from a pairs metadata dict (loaded at startup, same approach as ASSETS)
- Pass `order_ctx = {30d_high, 30d_low, last_close, max_leverage, lot_size, hl_symbol}` to the template

**Step 5: `POST /asset/{symbol}/order` in `web.py`** *(async endpoint)*
- Receives JSON body: `{side, order_type, size_usd, leverage, margin_type, reduce_only, tp_price, sl_price, testnet}`
- Calls `await place_order(...)` from `hl_order.py`
- Returns `{"ok": true, "order_id": "..."}` or `{"ok": false, "error": "..."}`

---

## Phase 2 — Template UI

**Step 6: New "Place Order" tab button** in `asset_detail.html`'s `btn-group`, after "Fundamentals" — `hx-vals='{"tab": "order"}'`

**Step 7: `{% elif tab == "order" %}` block** — Bootstrap 5 only, no extra JS libs:

| Control | Type | Default |
|---|---|---|
| Network | Toggle (Testnet/Mainnet) | Testnet |
| Margin type | Radio | Cross |
| Side | Radio | Sell/Short |
| Leverage | Range slider 1–max_leverage | 2× (Short) / 1× (Long) |
| Order type | Radio | Market |
| Limit price | Number (shown if Limit) | — |
| Size | Number (USD, 2dp) | — |
| Risk management | Radio | TP&SL |
| TP price | Number (shown if TP&SL) | 30D high |
| Gain % | Readonly calculated | auto |
| SL price | Number (shown if TP&SL) | 30D low |
| Loss % | Readonly calculated | auto |
| Levered P&L | Readonly display | auto (if leverage > 1) |

- JS: Mainnet selection → thick red border on form card
- JS: Side change → update leverage slider default (2↔1)
- JS: TP/SL price change → recalculate % fields and levered P&L live

**Step 8: Confirmation modal** — Bootstrap 5 modal, triggered by "Place Order" click:
- Populated client-side from form values (no server round-trip)
- **Confirm** → `fetch()` POST to `/asset/{symbol}/order` with JSON body → show result (green order ID or red error) inside modal
- **Cancel** → `modal.hide()` — no order placed

---

## Relevant Files
- `features/f16-place-order.md` — requirements
- `web.py` — new tab branch + new POST route
- `templates/asset_detail.html` — new tab button + order form block
- `pyproject.toml` — two new deps
- `hl_order.py` *(new file)*
- `.env` *(new file, gitignored)*
- `/work/projekte/hyperliquid-python/hl_client/src/hl_client/trading.py` — reference for `place_market_order` / `place_limit_order`

---

## Open Questions
1. **TP/SL bracket behavior**: plan places TP and SL as two separate reduce-only orders. If TP fills, the SL remains open (standard OCO-lite). Acceptable, or should a native bracket order be used if HL supports it?
