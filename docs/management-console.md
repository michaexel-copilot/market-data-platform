# Management Console

The management console is a single-page web application served at `GET /console` by the FastAPI backend. It provides a visual interface for browsing market data instruments, inspecting fundamental data, and (in future) triggering data refresh actions.

## Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  TOP_BAR                                                        │
│  Market Data — Management Console   [SEG_ASSET_CLASS]          │
├────────────────────┬────────────────────────────────────────────┤
│                    │ ACTION_BAR                                 │
│ PANE_INSTRUMENT    │ [BTN_UPDATE_FUNDAMENTALS] [BTN_UPDATE_OHLCV│
│ _LIST              │ ] [DDL_OHLCV_PERIOD]                      │
│                    ├────────────────────────────────────────────┤
│ ITEM_INSTRUMENT    │                                            │
│ ITEM_INSTRUMENT    │ PANE_FUNDAMENTALS                          │
│ ITEM_INSTRUMENT    │                                            │
│  ...               │  (key-value fundamental fields)           │
└────────────────────┴────────────────────────────────────────────┘
```

## UI Element Reference

Use these IDs to refer to specific elements in future refinement requests.

| Element ID | Type | Location | Description |
|---|---|---|---|
| `SEG_ASSET_CLASS` | Segmented button group | Top bar | Selects the active asset class. Buttons: `crypto` (default), `equity`, `etf`, `fx`, `commodity`. Switching class reloads `PANE_INSTRUMENT_LIST`. |
| `PANE_INSTRUMENT_LIST` | Panel (left side) | Main layout | Scrollable list of active instruments for the selected asset class. |
| `ITEM_INSTRUMENT` | List item | Inside `PANE_INSTRUMENT_LIST` | One row per instrument. Shows `ticker` (bold) and `full_name`. Has `.selected` state when active. Click triggers fundamentals load. |
| `PANE_FUNDAMENTALS` | Panel (main/right area) | Main layout | Displays fundamental data for the selected instrument as a key-value table. Shows placeholder when no instrument is selected. |
| `ACTION_BAR` | Toolbar | Above `PANE_FUNDAMENTALS` | Contains the action buttons. All controls disabled until an instrument is selected. |
| `BTN_UPDATE_FUNDAMENTALS` | Button | `ACTION_BAR` | "Update Fundamental Data" — triggers a fundamentals refresh for the selected instrument. **Stub only** — logs to console. Enabled when instrument selected. |
| `BTN_UPDATE_OHLCV` | Button | `ACTION_BAR` | "Update OHLCV Data" — triggers an OHLCV refresh for the selected instrument using the period from `DDL_OHLCV_PERIOD`. **Stub only** — logs to console. Enabled when instrument selected. |
| `DDL_OHLCV_PERIOD` | Dropdown (`<select>`) | `ACTION_BAR`, adjacent to `BTN_UPDATE_OHLCV` | Period selector for OHLCV updates. Options: `1m`, `5m`, `1h`, `1d` (default), `1w`, `1mo`, `1y`. Enabled when instrument selected. |

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

## Extending Button Logic

To implement `BTN_UPDATE_FUNDAMENTALS`, replace the stub handler in `src/market_data/api/rest/console.py`:

```js
// Current stub:
btnFundamentals.addEventListener('click', () => {
  console.log(`[stub] BTN_UPDATE_FUNDAMENTALS clicked for ${selectedInstrumentId}`);
});
```

Add a `POST /v1/instruments/{id}/refresh-fundamentals` backend route, then replace the stub with a `fetch()` call to that endpoint.

Similarly for `BTN_UPDATE_OHLCV` — add `POST /v1/instruments/{id}/refresh-ohlcv?interval={period}` and wire to the button handler.
