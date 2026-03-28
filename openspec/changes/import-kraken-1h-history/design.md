## Context

The database holds 1h OHLCV candles starting from when continuous live ingestion began
(typically 2023–2024), but most crypto assets have `launch_date` values going back to
2017–2020. Kraken provides freely downloadable historical OHLCV flat files
(`{PAIR}_60.csv`, headerless, unix-timestamp-ordered) covering from launch to present,
mounted at `/mnt/ds420/data/kraken/1-hour/`.

The existing `import_cryptocompare` script (migration 025, `data_source_id = 4`) is the
direct template for this work: it reads a flat file, upserts into `ohlcv`, and updates
`ohlcv_data_available`. The Kraken import is simpler — no staging table needed because
the Kraken format maps directly to the `ohlcv` schema with no intermediate
transformation step.

The `instruments` table holds `ticker` (e.g. `ADA`) for each canonical `instrument_id`
(e.g. `cardano`). The symbol resolver already does a loose ticker match, so ShortDesk
can pass `ADA` → platform resolves → `cardano`.

## Goals / Non-Goals

**Goals:**
- Register Kraken Historical as a named data source (migration 031, `data_source_id = 5`)
- Map `instrument_id` → Kraken pair via a YAML override file; fallback is `{TICKER}USD`
- Provide a CLI tool (`import-kraken-1h`) that reads the CSV and upserts gap rows
- Provide two REST endpoints: gap-status (GET) and trigger-import (POST)
- Show a compact status badge in the ShortDesk Fundamentals card
- Show an "Import Kraken 1h" button in the Strategy Controls action area

**Non-Goals:**
- Automatic/scheduled ingestion — import is always manual (on-demand via button or CLI)
- Importing intervals other than 1h (Kraken also publishes 1m, 1d — out of scope)
- Fetching Kraken data via API — file-based only
- Modifying existing live-ingestion pipelines
- Deriving 1d aggregates from imported rows (the existing `cryptocompare` script does
  this; Kraken daily can be fetched live if needed)

## Decisions

### D1 — No staging table (direct upsert)

**Decision**: Upsert Kraken rows directly into `ohlcv`; do not create a staging table.

**Rationale**: The CryptoCompare staging table exists because CC data uses a non-canonical
instrument ID (`BTC-USD`) that must be remapped to `bitcoin`. Kraken data uses the
`instruments.ticker` as a prefix, and the canonical `instrument_id` is resolved before
the import runs — no remapping step is needed. A staging table would add complexity
without benefit.

**Alternative considered**: Stage-then-migrate (like `import_cryptocompare`). Rejected
because it requires an extra table migration and a two-step CLI workflow for no gain.

---

### D2 — Pair mapping: YAML override, `{TICKER}USD` default

**Decision**: A file `src/market_data/config/kraken_pairs.yaml` lists only the exceptions
to the `{TICKER}USD` default:
```yaml
# Maps canonical instrument_id → Kraken pair (filename prefix)
# Only list exceptions to {TICKER}USD convention
bitcoin: XBTUSD
```
At runtime: look up `instrument_id` in YAML; if absent, construct `{ticker.upper()}USD`.
If the resulting file doesn't exist in the data directory, report `has_file: false`.

**Rationale**: The vast majority of pairs follow `{TICKER}USD` (ADAUSD, ETHUSD, SOLUSD…).
A full lookup table would require maintaining O(100) entries for a handful of exceptions.
The YAML is user-editable and self-documenting.

**Alternative considered**: DB table `kraken_pair_map`. Rejected — adds a migration, no
query-time benefit, harder to edit than a YAML file.

---

### D3 — REST endpoints on market-data-platform (not ShortDesk-direct)

**Decision**: Two new endpoints on the platform:
- `GET  /v1/instruments/{symbol}/kraken-1h-status`
- `POST /v1/instruments/{symbol}/import-kraken-1h`

ShortDesk calls these; neither touches the DB or filesystem directly.

**Rationale**: `/mnt/ds420/` is accessible from the platform process. Keeping DB writes
in the platform preserves the existing architecture contract (ShortDesk = UI only,
market-data-platform = data layer). The platform already uses `resolve_symbol()` to
map HL symbol → canonical `instrument_id`.

**Alternative considered**: ShortDesk imports directly (bypassing platform). Rejected —
ShortDesk has no DB connection and the path `/mnt/ds420/` being accessible from the
platform process is confirmed.

---

### D4 — Gap detection via `MIN(ts)` in `ohlcv`

**Decision**: The gap-status endpoint computes:
```sql
SELECT MIN(ts) FROM ohlcv
WHERE instrument_id = %s AND interval = '1h' AND source != 'kraken'
```
Gap = rows in CSV with `ts < MIN(ts)` above (or all CSV rows if no 1h data exists).
The endpoint returns `{ has_file, kraken_pair, launch_date, earliest_db_ts, gap_rows }`.

**Rationale**: Simple, no extra columns. The `source = 'kraken'` exclusion prevents
double-counting after a partial import.

---

### D5 — ShortDesk UI: badge in Fundamentals card, button next to "Find Best SMA"

**Decision**:
- Status badge: new card in the Fundamentals `div.row.g-3` row, compact, shows one of:
  three states (no file / gap / complete) as Bootstrap badge colours (warning / info / success).
- Import button: placed in the same `div.mb-3` block as "Find Best SMA" (Strategy Controls
  accordion). Uses HTMX `hx-post` + `hx-target` to show the import result inline.

**Rationale**: The "Find Best SMA" button is the existing precedent for action buttons.
The Fundamentals row already has a card-per-datum pattern.

## Risks / Trade-offs

- **Large CSV parse time** — ADAUSD alone has 63,291 rows; a full import for all assets
  could be millions of rows. Mitigation: batch upserts (`_BATCH_SIZE = 5000`, same as
  import_cryptocompare); the POST endpoint is synchronous but fast enough for one asset
  at a time via the UI.

- **Partial import / re-import** — if the user clicks the button twice, the `ON CONFLICT
  DO UPDATE` upsert is idempotent; no duplicate rows. Source field stays `'kraken'`.

- **File naming edge cases** — Kraken uses `XBT` for Bitcoin; other assets may have
  similar quirks (e.g. `XXBT`, `XETH`). The YAML override handles known cases; unknown
  cases return `has_file: false` with the attempted filename shown in the badge so the
  user knows what to rename.

- **`launch_date` absent** — some instruments may have `NULL` launch_date. The gap-status
  endpoint still works: it uses `MIN(ts)` from the CSV file itself as the gap start when
  `launch_date` is NULL.

## Migration Plan

1. Run migration `031_kraken_historical_source.sql` (`migrate` CLI)
2. Deploy updated market-data-platform (new endpoints + script entry point)
3. Drop CSV files in `/mnt/ds420/data/kraken/1-hour/`
4. Use UI button (or `import-kraken-1h --symbol ADA`) per asset
5. No rollback needed — rows are additive; remove with
   `DELETE FROM ohlcv WHERE source = 'kraken' AND instrument_id = %s` if needed

## Open Questions

_(none — all decisions resolved during exploration)_
