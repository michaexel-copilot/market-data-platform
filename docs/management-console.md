# Management Console

The management console is a single-page web application served at `GET /console` by the FastAPI backend. It provides a visual interface for browsing market data instruments, inspecting fundamental data, and triggering OHLCV imports from locally-cached provider data.

## Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  TOP_BAR                                                        │
│  Market Data — Management Console   [SEG_ASSET_CLASS]          │
├────────────────────┬────────────────────────────────────────────┤
│ INP_INSTRUMENT_    │ ACTION_BAR                                 │
│ FILTER             │ [BTN_UPDATE_FUNDAMENTALS] [BTN_UPDATE_OHLCV│
│                    │ ]                                          │
│ PANE_INSTRUMENT    ├────────────────────────────────────────────┤
│ _LIST              │                                            │
│                    │ PANE_FUNDAMENTALS                          │
│ ITEM_INSTRUMENT    │   key-value fundamental fields             │
│ ITEM_INSTRUMENT    │   OHLCV Time Range (ohlcv-range-section)  │
│ ITEM_INSTRUMENT    │   OHLCV Data Available matrix              │
│  ...               │                                            │
└────────────────────┴────────────────────────────────────────────┘
```

## UI Element Reference

Use these IDs to refer to specific elements in future refinement requests.

| Element ID | Type | Location | Description |
|---|---|---|---|
| `SEG_ASSET_CLASS` | Segmented button group | Top bar | Selects the active asset class. Buttons: `crypto` (default), `equity`, `etf`, `fx`, `commodity`. Switching class reloads `PANE_INSTRUMENT_LIST`. |
| `PANE_INSTRUMENT_LIST` | Panel (left side) | Main layout | List of active instruments for the selected asset class. Only the list body scrolls; the header and filter remain pinned. On startup, Bitcoin (`BTC`) is auto-selected if present. |
| `INP_INSTRUMENT_FILTER` | Text input | Top of `PANE_INSTRUMENT_LIST` (pinned) | Filters the instrument list by ticker or name as you type. Always visible regardless of scroll position. |
| `ITEM_INSTRUMENT` | List item | Inside `PANE_INSTRUMENT_LIST` | One row per instrument. Shows `ticker` (bold) and `full_name`. Has `.selected` state when active. Click triggers fundamentals load. |
| `PANE_FUNDAMENTALS` | Panel (main/right area) | Main layout | Displays fundamental data for the selected instrument as a key-value table, followed by the OHLCV Time Range section and OHLCV Data Available matrix. Shows placeholder when no instrument is selected. |
| `ACTION_BAR` | Toolbar | Above `PANE_FUNDAMENTALS` | Contains the action buttons. All controls disabled until an instrument is selected. |
| `BTN_UPDATE_FUNDAMENTALS` | Button | `ACTION_BAR` | "Update Fundamental Data" — triggers a fundamentals refresh. **Stub only** — logs to console. |
| `BTN_UPDATE_OHLCV` | Button | `ACTION_BAR` | "Update OHLCV Data" — triggers a smart multi-step OHLCV update via `POST /v1/admin/smart-update-ohlcv`: (1) 1h freshness check, (2) conditional 1h ingest if stale, (3) Binance 1m gap detection and fill, (4) 1m→1h aggregation of synthetic candles. Shows per-step inline status. Re-enables after the request completes. |

## Smart OHLCV Update Flow

When `BTN_UPDATE_OHLCV` is clicked, the console:

1. POSTs to `POST /v1/admin/smart-update-ohlcv` with `{ instrument_id }`.
2. The backend runs the following steps automatically:
   - **1h_freshness_check** — queries `MAX(ts)` at `interval = '1h'`. If `NULL` or older than 5 hours, status is `"stale"`.
   - **1h_ingest** — if stale, triggers the `ohlcv_1h` ingestion job for the instrument.
   - **1m_gap_check** — queries `MAX(ts)` at `interval = '1m'`; computes gap to now.
   - **binance_availability** — checks `ohlcv_data_available JOIN data_source` for `has_1m = TRUE AND short_name = 'binance'`.
   - **1m_fetch** — if gap and Binance available, calls `BinanceConnector.fetch_ohlcv`.
   - **1h_aggregation** — aggregates fetched 1m records into synthetic 1h candles (`is_aggregated = TRUE`) and persists them.
3. On success, an inline per-step summary is shown and the OHLCV sections refresh.
4. If Binance is unavailable for the instrument, gap fill steps are skipped with a note.
5. On any HTTP or network error, "OHLCV update failed: \<error\>" is displayed.

## OHLCV Time Range Section

After the key-value fundamentals table, `PANE_FUNDAMENTALS` shows an **OHLCV Time Range** table with columns **Interval / First / Last**. Timestamps are displayed as `YYYY-MM-DD HH:MM` (UTC). This section refreshes automatically after a successful OHLCV import.

## Usage

Start the API server:

```bash
uv run serve
# or
uv run uvicorn market_data.api.rest.app:app --reload
```

Then open [http://localhost:8010/console](http://localhost:8010/console) in your browser (or replace `8010` with your `HTTP_PORT` value).

## REST Endpoints Used by the Console

| Endpoint | Purpose |
|---|---|
| `GET /v1/instruments?asset_class=<class>&is_active=true&page_size=200` | Populate `PANE_INSTRUMENT_LIST` |
| `GET /v1/instruments/{instrument_id}/fundamentals` | Populate `PANE_FUNDAMENTALS` |
| `GET /v1/instruments/{instrument_id}/ohlcv-availability` | OHLCV Time Range section |
| `GET /v1/instruments/{instrument_id}/ohlcv-data-available` | OHLCV Data Available matrix |
| `POST /v1/admin/smart-update-ohlcv` | Smart OHLCV update (`BTN_UPDATE_OHLCV`) |

---

## Admin Endpoints

All admin endpoints are under `/v1/admin/`. They perform long-running database operations
and are designed to be called from the CLI or from automation scripts.

> **Note:** All CLI commands delegate to these endpoints instead of opening a direct
> DuckDB connection. This avoids the "database is locked" error when the REST service
> is already running. Set `MARKET_DATA_URL` (default: `http://localhost:8010`) to point
> CLIs at a non-default server.

---

### POST /v1/admin/compute-indicators

Compute strategy indicator values for one or all active instruments and persist them
to the `trading_strategies` table.

**Request body** (JSON):

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `strategy` | string | yes | — | Strategy name, e.g. `best_sma` |
| `symbol` | string | no | null | Ticker symbol. Omit to run for all active instruments. |
| `sl_short` | float | no | 10.0 | Stop-loss % for short strategy |
| `sl_long` | float | no | 10.0 | Stop-loss % for long strategy |
| `pos_usd` | float | no | 100.0 | Position size in USD |

**Example request:**
```bash
curl -s -X POST http://localhost:8010/v1/admin/compute-indicators \
  -H "Content-Type: application/json" \
  -d '{"strategy": "best_sma", "symbol": "BTC"}'
```

**Example response (HTTP 200):**
```json
{
  "ok": 1,
  "errors": 0,
  "results": [
    { "ticker": "BTC", "status": "ok", "elapsed_s": 0.42 }
  ]
}
```

**Error responses:**
- `422` — unknown strategy name: `{"detail": "Unknown strategy 'foo'. Available: best_sma"}`
- `404` — symbol not found: `{"detail": "Symbol 'XYZ' not found"}`

**CLI equivalent:**
```bash
# All active instruments
uv run compute-indicators --strategy best_sma

# Single instrument
uv run compute-indicators --strategy best_sma --symbol BTC

# Custom stop-loss and position size
uv run compute-indicators --strategy best_sma --sl-short 5 --sl-long 8 --pos-usd 200

# Against a non-default server
uv run compute-indicators --strategy best_sma --url http://myserver:9000
# or: MARKET_DATA_URL=http://myserver:9000 uv run compute-indicators --strategy best_sma
```

Exit code: `0` if all instruments succeeded, `1` if any errors.

---

### POST /v1/admin/import-cmc-static

Import pre-downloaded CoinMarketCap static TSV snapshots from the server filesystem
into DuckDB. The import is idempotent — already-processed snapshots are skipped.

**Request body** (JSON):

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `dir` | string | no | `$CMC_STATIC_DIR` | Directory containing `*_listing_data.tsv` snapshot files. Falls back to the server-side `CMC_STATIC_DIR` env var if omitted. |

**Example request:**
```bash
curl -s -X POST http://localhost:8010/v1/admin/import-cmc-static \
  -H "Content-Type: application/json" \
  -d '{"dir": "/data/cmc-snapshots"}'
```

**Example response (HTTP 200):**
```json
{
  "listing": 150,
  "map": 148,
  "categories": 12,
  "category_coins": 890,
  "skipped": 2
}
```
An empty object `{}` is returned if no snapshots were found in the directory.

**Error responses:**
- `422` — no directory configured: `{"detail": "No directory specified and CMC_STATIC_DIR is not set"}`
- `422` — directory not found: `{"detail": "Directory does not exist: /invalid/path"}`

**CLI equivalent:**
```bash
# Use server-side CMC_STATIC_DIR env var
uv run market-data import-cmc-static

# Explicit directory (passed to the server)
uv run market-data import-cmc-static /data/cmc-snapshots

# Against a non-default server
uv run market-data import-cmc-static --url http://myserver:9000
# or: MARKET_DATA_URL=http://myserver:9000 uv run market-data import-cmc-static
```

Exit code: `0` on success, `1` on error.
