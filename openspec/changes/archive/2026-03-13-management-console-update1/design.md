## Context

The management console (served at `/console`) currently has a read-only view of instruments and a stub action bar. Fundamental data lives in `instruments` + per-class tables (`instrument_crypto`, etc.) but there is no record of *which data source* supplied each field or *when* it was last refreshed. CoinMarketCap static data already exists in staging tables (`cmc_listing_snapshots`, `cmc_map`) but is not fully promoted into the canonical tables. Tickers are ambiguous across providers (e.g. `BTC` on CoinMarketCap vs Hyperliquid may map to different objects).

## Goals / Non-Goals

**Goals:**
- Add `data_source` table to register known providers with priority ordering
- Add `attribute_source_map` to record per-attribute provenance and last-updated timestamps
- Add `ticker_source_map` to resolve ambiguous ticker ↔ instrument mappings per data source
- Expose a `POST /v1/admin/migrate-fundamentals` endpoint that runs the CMC → canonical promotion logic
- Add an "Action Button List" (right-aligned) in the console top bar with a `BTN_MIGRATE_FUNDAMENTALS` button
- Wire the instrument list click to show fundamentals in the main pane (already partially implemented)

**Non-Goals:**
- Multi-source reconciliation logic beyond CoinMarketCap (future work)
- Real-time streaming of migration progress to the browser
- Authentication/authorization on admin endpoints (out of scope for this iteration)

## Decisions

### D1 — Three new tables, not a single wide provenance column

**Decision:** Use three separate tables (`data_source`, `attribute_source_map`, `ticker_source_map`) rather than embedding provenance as JSON in `instruments`.

**Rationale:** Allows querying "which instruments have stale CMC data" without JSON scanning; enables future multi-source priority ordering cleanly; aligns with existing normalized schema style.

**Alternative considered:** A `data_sources` JSON column on `instruments` already exists but is write-once and not queryable for attribute-level provenance.

---

### D2 — `attribute_source_map` keyed by `(instrument_id, attribute_name)`

**Decision:** Each row records one `(instrument_id, attribute_name, data_source_id, last_updated_at)`. `attribute_name` is a plain VARCHAR matching the canonical column name (e.g. `ticker`, `full_name`, `launch_date`, `cmc_rank`).

**Rationale:** Simple to populate in migration code; attribute names are stable column names from known tables; low cardinality per instrument.

**Alternative considered:** A foreign key to a `attribute_definition` table adds schema overhead with no benefit at this scale.

---

### D3 — `ticker_source_map` for cross-source disambiguation

**Decision:** New table `ticker_source_map(instrument_id, data_source_id, source_ticker, is_canonical)` to store the ticker as known to each data source.

**Rationale:** CoinMarketCap uses `symbol` (e.g. `BTC`) which can clash with Hyperliquid's `BTC-perp` derivative. Storing the source-specific ticker per instrument makes future resolution deterministic.

---

### D4 — Migration endpoint is synchronous and idempotent

**Decision:** `POST /v1/admin/migrate-fundamentals` runs synchronously, returns a JSON summary (`{promoted: N, skipped: N, errors: []}`), and is safe to call multiple times (upsert semantics).

**Rationale:** Snapshot sizes are small (thousands of rows); async job infra is not available; idempotency prevents double-promotion.

---

### D5 — `data_source` priority: 0 = highest, `NULL` = disabled

**Decision:** `retrieval_priority INTEGER` with `NULL` meaning "do not use as an active source".

**Rationale:** Null signals opt-out cleanly without a magic sentinel integer; priority 0 meaning "highest" is conventional in config systems.

## Risks / Trade-offs

- [Risk] Admin endpoint has no authentication → Only accessible on local/internal network; acceptable for a development-stage platform. → Mitigation: document this assumption; a future auth layer can wrap it.
- [Risk] Synchronous migration may block if snapshot data is very large → Mitigation: migration is scoped to latest snapshot only; typical CMC listing has ~10k rows which complete in <1s.
- [Risk] `attribute_name` as a raw VARCHAR has no referential integrity → Mitigation: migration code uses a whitelist of known attribute names.

## Migration Plan

1. Run new DB migrations (012, 013, 014) — additive, no destructive changes.
2. Seed `data_source` table with CoinMarketCap as the first entry.
3. Deploy updated FastAPI app with new console UI and admin endpoint.
4. Operator clicks "Migrate Fundamental Data" → endpoint runs, populates `attribute_source_map` and `ticker_source_map`.
5. Rollback: drop tables 012–014; remove new endpoint; revert console HTML. Existing data is unaffected.
