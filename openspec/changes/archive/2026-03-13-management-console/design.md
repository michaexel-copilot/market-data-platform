## Context

The market data platform has a functional REST/gRPC/JSON-RPC backend and a DuckDB data store. Currently there is no visual interface — all interactions require direct API calls or raw SQL. Operators need a way to browse instruments by asset class, inspect fundamental data, and trigger data refresh actions.

The existing FastAPI app (`src/market_data/api/rest/app.py`) already exposes `GET /v1/instruments` (with `asset_class` filter), `GET /v1/instruments/{symbol}`, and `GET /v1/instruments/{symbol}/fundamentals`. These endpoints can be consumed directly by the console UI.

## Goals / Non-Goals

**Goals:**
- Serve a single-page web console at `GET /console` from the existing FastAPI app
- Asset-class segmented selector (default: crypto)
- Left pane: scrollable instrument list filtered by selected asset class
- Main pane: fundamentals detail for the selected instrument
- Action button bar with named, stub buttons: `BTN_UPDATE_FUNDAMENTALS` and `BTN_UPDATE_OHLCV` (with period dropdown `DDL_OHLCV_PERIOD`)
- No external build toolchain — vanilla HTML/CSS/JS served as a single embedded template string or static file

**Non-Goals:**
- Implementing actual button logic (backend refresh actions) — buttons are named stubs only
- Authentication / authorisation for the console
- Mobile responsiveness (desktop-first)
- Real-time WebSocket updates

## Decisions

### 1. Serve UI from FastAPI using HTMLResponse / Jinja2

**Decision:** Serve the console as a single `GET /console` route returning an `HTMLResponse` with an inline HTML/JS page.

**Rationale:** Avoids introducing a Node.js build pipeline or separate static file server. The entire UI fits in a single file given its scope. FastAPI's `HTMLResponse` is sufficient.

**Alternative considered:** Separate frontend project (React/Vite) — rejected as overkill for a management utility of this size.

### 2. Vanilla JS with fetch() calls to existing REST endpoints

**Decision:** The console JS calls `GET /v1/instruments?asset_class=<class>` for the instrument list and `GET /v1/instruments/{id}/fundamentals` for detail data. No new backend endpoints are needed for the read path.

**Rationale:** The existing REST API already provides exactly what the UI needs. Adding a thin JS layer is simpler than new backend routes.

### 3. Action buttons are named stubs only

**Decision:** Buttons are rendered with `id` attributes matching the reference names (`BTN_UPDATE_FUNDAMENTALS`, `BTN_UPDATE_OHLCV`, `DDL_OHLCV_PERIOD`) and click handlers that log a console message only.

**Rationale:** The feature spec explicitly defers logic implementation. Naming the elements now guarantees stable reference IDs for future refinement.

### 4. New console router in `src/market_data/api/rest/console.py`

**Decision:** Add a dedicated `console.py` router (similar to `instruments.py` / `ohlcv.py`) and mount it in `app.py`.

**Rationale:** Keeps the app factory clean and follows existing conventions.

## Risks / Trade-offs

- [Risk] Inline HTML grows unwieldy as the UI evolves → Mitigation: extract to a `templates/console.html` file when needed; the router will load it from disk
- [Risk] Existing REST endpoints return paginated results (default 50) — the instrument list may be incomplete for large databases → Mitigation: UI fetches with `page_size=200` per asset class for now; pagination can be added later
