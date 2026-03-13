## 1. Backend — Console Route

- [x] 1.1 Create `src/market_data/api/rest/console.py` with a `GET /console` route returning `HTMLResponse`
- [x] 1.2 Mount the console router in `src/market_data/api/rest/app.py`

## 2. Frontend — Console HTML/JS

- [x] 2.1 Implement the asset-class segmented button bar (`SEG_ASSET_CLASS`) with values `crypto`, `equity`, `etf`, `fx`, `commodity`; default active: `crypto`
- [x] 2.2 Implement the instrument list pane (`PANE_INSTRUMENT_LIST`) that fetches `GET /v1/instruments?asset_class=<class>&page_size=200` on asset-class change and renders ticker + full name rows
- [x] 2.3 Highlight the selected instrument row (`ITEM_INSTRUMENT`) on click
- [x] 2.4 Implement the fundamentals detail pane (`PANE_FUNDAMENTALS`) that fetches `GET /v1/instruments/{symbol}/fundamentals` on instrument selection and renders key-value pairs
- [x] 2.5 Show placeholder "Select an instrument to view details" in `PANE_FUNDAMENTALS` when no instrument is selected
- [x] 2.6 Show "No instruments found" in `PANE_INSTRUMENT_LIST` when the API returns an empty list
- [x] 2.7 Implement the action button bar with `BTN_UPDATE_FUNDAMENTALS` (disabled until instrument selected)
- [x] 2.8 Implement `BTN_UPDATE_OHLCV` button and `DDL_OHLCV_PERIOD` dropdown with options `1m`, `5m`, `1h`, `1d`, `1w`, `1mo`, `1y` (both disabled until instrument selected)
- [x] 2.9 Wire `BTN_UPDATE_FUNDAMENTALS` click stub: log `[stub] BTN_UPDATE_FUNDAMENTALS clicked for <id>`
- [x] 2.10 Wire `BTN_UPDATE_OHLCV` click stub: log `[stub] BTN_UPDATE_OHLCV clicked for <id>, period=<value>`

## 3. Documentation

- [x] 3.1 Create `docs/management-console.md` with layout description and UI element reference table
