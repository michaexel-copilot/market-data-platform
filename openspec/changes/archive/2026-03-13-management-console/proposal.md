## Why

Operating the platform (browsing instruments, inspecting fundamentals, triggering refreshes) currently requires raw SQL or API calls. A web-based management console gives operators a visual interface to navigate assets, inspect reference data, and dispatch data-update actions without needing access to the underlying database or CLI.

## What Changes

- Add a single-page web application served by the existing FastAPI backend at `/console`
- Add a backend endpoint that serves the console HTML/JS/CSS as a static bundle
- Expose thin REST endpoints required by the console: asset-class listing, per-instrument fundamentals, and action triggers for data refresh
- No breaking changes to existing REST, gRPC, or JSON-RPC contracts

## Capabilities

### New Capabilities

- `management-console`: Browser-based UI for the market data platform — asset-class selector, instrument list pane, fundamentals detail pane, and an action button bar with named buttons for triggering data updates

### Modified Capabilities

- `unified-market-data-api`: Add console-serving endpoint (`GET /console`) and any new REST sub-routes required by the UI (e.g., `GET /api/v1/instruments?asset_class=crypto`, `POST /api/v1/instruments/{id}/refresh-fundamentals`, `POST /api/v1/instruments/{id}/refresh-ohlcv`)

## Impact

- **FastAPI app** (`src/market_data/api/rest/`): new route file for console UI and new action endpoints
- **Frontend**: static HTML/CSS/JS bundle (no build step required — vanilla JS or a lightweight framework already available in the venv)
- **No database schema changes**
- **No connector changes**
