## Why

The instrument list in the management console can contain thousands of entries (e.g. all CMC crypto coins). Finding a specific instrument requires scrolling through the entire list; a live filter lets operators locate instruments instantly by typing part of a ticker or name.

## What Changes

- Add a text input field (`INP_INSTRUMENT_FILTER`) above the instrument list in `PANE_INSTRUMENT_LIST`
- Filter the rendered list client-side as the user types, matching against `ticker` and `full_name` (case-insensitive)
- No backend or API changes required — filtering operates on the already-loaded in-memory list

## Capabilities

### New Capabilities

*(none — this is a pure UI enhancement)*

### Modified Capabilities

- `management-console`: Add instrument list filter input requirement

## Impact

- **Console UI** (`src/market_data/api/rest/console.py`): HTML/CSS/JS changes only — new input element and filter logic
- No backend, API, database, or spec changes outside the management-console spec
