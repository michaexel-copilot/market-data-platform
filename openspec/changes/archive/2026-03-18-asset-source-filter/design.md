## Context

The management console today loads instruments filtered only by asset class and text search. The
`data_source` table has two seeded rows (`cmc`, `eodhd`); Hyperliquid instruments live in a
separate `instrument_hyperliquid` table with no corresponding `data_source` entry. A pre-computed
intersection CSV exists at `/appdata/static_data/cc_hl_intersection.csv` listing instruments
available on both EODHD and Hyperliquid (columns: `base`, `eodhd_code`, `hl_symbol`). The
management console is a server-rendered page with **vanilla JavaScript** (no HTMX); interactive
updates go through `fetch()` calls wired to named DOM elements.

## Goals / Non-Goals

**Goals:**
- New `instrument_source_intersection` table tracking which data sources cover each instrument
- Seed it from the existing CSV via a one-shot CLI command
- Add `hl` as a `data_source` row (prerequisite for using a unified short-name)
- Extend `GET /v1/instruments?sources=` to filter by intersection
- Add `SEG_SOURCE_FILTER` button bar to the management console (second row under `SEG_ASSET_CLASS`)

**Non-Goals:**
- Generating or updating the EODHD asset list (deferred)
- Yahoo Finance or other new sources
- Automated re-sync of the intersection table from live APIs
- Changes to ShortDesk

## Decisions

### 1. New table vs. reusing `ohlcv_data_available`

`ohlcv_data_available` tracks *interval availability* per source (has_1h, has_1d, …), not
instrument-level membership. Using it for source filtering would couple two independent concerns
and exclude instruments that are registered with a source but have no OHLCV yet. A dedicated
`instrument_source_intersection` table is cleaner and independently evolve-able.

**Chosen**: new table.

### 2. Schema: normalized rows vs. array column

Options:
- **Normalized rows** `(instrument_id, source_short_name)` composite PK — one row per
  instrument-source pair. Intersection query uses `GROUP BY … HAVING COUNT = N`.
- **Array column** `sources TEXT[]` — single row per instrument, array operator `@>`.

Normalized rows are easier to update individual sources (add/remove one source without rewriting
the whole array) and avoid array-operator syntax differences across DuckDB/PostgreSQL. All
current SQL in this codebase uses standard relational patterns.

**Chosen**: normalized rows; schema:
```sql
CREATE TABLE instrument_source_intersection (
    instrument_id       TEXT    NOT NULL REFERENCES instruments(instrument_id),
    source_short_name   TEXT    NOT NULL,
    PRIMARY KEY (instrument_id, source_short_name)
);
```

### 3. `hl` data_source row

Hyperliquid has no `data_source` row today. The intersection table uses `source_short_name` as a
free-text key. To keep things consistent with `ohlcv_data_available` (which uses `data_source_id`
FK), we add a `hl` row in a new migration before seeding the intersection table.

**Chosen**: migration `023_hl_data_source.sql` seeds `(3, 'Hyperliquid', 'hl', …)`.
Migration `024_instrument_source_intersection.sql` creates the table.

### 4. Intersection query approach

```sql
SELECT i.*
FROM instruments i
JOIN instrument_source_intersection isi ON isi.instrument_id = i.instrument_id
WHERE isi.source_short_name = ANY(%s)   -- bound array from ?sources= param
GROUP BY i.instrument_id, …
HAVING COUNT(DISTINCT isi.source_short_name) = %s  -- len(sources)
```

Added as a conditional JOIN block inside the existing `list_instruments` repository function.
When `sources` is omitted or empty the JOIN is skipped — no behavioural change for existing
callers.

### 5. Console update mechanism

The console uses vanilla `fetch()` driven by JS event listeners, not HTMX. The existing
`loadInstruments(assetClass)` function already builds a URL and populates `PANE_INSTRUMENT_LIST`.
The new `SEG_SOURCE_FILTER` button bar updates a module-level `activeSources` set; clicking any
button calls `loadInstruments` with the current class and appends `&sources=<csv>` to the URL.

Default state on page load: `activeSources = new Set(['eodhd', 'hl'])`.

## Risks / Trade-offs

- **Stale intersection table** — the CSV is a point-in-time snapshot; new instruments added to
  EODHD or Hyperliquid after the last CSV refresh won't appear. → Document re-seeding in
  management-console.md; accept staleness until automated sync is built.
- **`hl` short-name coupling** — using `hl` in both `data_source.short_name` and the button
  label couples UI to DB. → Keep `hl` as the canonical short-name throughout; change in one
  place.
- **Empty intersection after migration** — if `import-source-intersection` hasn't been run, the
  `?sources=eodhd,hl` default returns zero results. → Console shows "No instruments found"
  message (already handled). Add a visible warning if `instrument_source_intersection` is empty.
- **DuckDB compatibility** — ~~DuckDB is no longer in use; `migrate-to-postgresql-timescaledb`
  is complete. PostgreSQL-only migrations are the sole target.~~ **Resolved.**

## Migration Plan

1. Run `uv run migrate` — applies migrations 023 and 024 in order
2. Run `uv run import-source-intersection` — seeds the table from
   `/appdata/static_data/cc_hl_intersection.csv`; idempotent (uses `ON CONFLICT DO NOTHING`)
3. Restart `uv run serve` — picks up new API parameter and updated console HTML
4. Verify: open console, confirm button bar visible, toggle sources, confirm list updates

**Rollback**: drop `instrument_source_intersection` table and revert the migrations; remove
the `?sources=` branch from `list_instruments` (no data loss — the table is derived from the CSV).

## Open Questions

- Should `SEG_SOURCE_FILTER` be hidden when no asset class is selected, or always visible?
  → Propose: always visible; defaults (eodhd + hl) apply regardless of asset class.
- Should an invalid `sources` value (unknown short-name) return 400 or silently return empty?
  → Propose: return empty (`HAVING COUNT = N` will simply match zero rows); simpler, no
  validation overhead.
