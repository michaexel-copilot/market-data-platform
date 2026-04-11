## Context

The OHLCV time-range table in the management console showed first/last timestamps per interval but gave the operator no per-interval control. The single global "Update OHLCV Data" button triggered a multi-step smart refresh across all intervals, which made it hard to refresh just the stale layer. It also hid an important state: for instruments with no ingested `1m` rows, the `1m` interval was absent entirely.

During implementation, two operational risks became clear:
- derived updates must only aggregate from a **newer** lower interval, otherwise the UI can report a misleading successful refresh;
- all `1m` writes must populate `tick_1m`, or PostgreSQL rejects the row via `ohlcv_tick_1m_not_null`.

## Goals / Non-Goals

**Goals**
- Make `1m` visibility explicit in the console even when no 1m candles exist yet.
- Add row-level `Update` and `Auto` controls for native intervals (`1m`, `5m`, `1h`, `1d`).
- Persist per-instrument per-interval auto-update preferences.
- Ensure derived updates only use fresher lower-resolution data and provide actionable errors otherwise.

**Non-Goals**
- Do not remove the existing global smart-update action.
- Do not introduce a new third-party provider for live `1m` data beyond Binance.
- Do not auto-backfill historical low-resolution gaps beyond the existing manual and scheduler flows.

## Decisions

### Decision: Persist `auto_update` in a dedicated settings table

**Chosen:** `ohlcv_update_settings(instrument_id, interval, auto_update)` with a composite primary key.

**Why:** The setting is orthogonal to candle data and should survive OHLCV rewrites, backfills, and archival. A separate table keeps the contract simple for `GET`/`PUT` UI calls.

### Decision: Keep per-interval manual refresh on the instruments API

**Chosen:** `POST /v1/instruments/{symbol}/update-ohlcv/{interval}`.

**Why:** The action is scoped to one instrument row and one interval, so colocating it with the instrument detail endpoints keeps the contract discoverable and avoids overloading the admin smart-update endpoint.

### Decision: Use Binance for live `1m` refresh and lower-interval aggregation for derived refreshes

**Chosen:**
- `1m` → fetch from Binance and write native rows.
- `5m`, `1h`, `1d` → aggregate from the best available **newer** lower interval already stored in the database.

**Why:** This matches the operator workflow: refresh the base (`1m`) first when needed, then derive coarser intervals locally without unnecessary external calls.

## Risks / Trade-offs

- Instruments not traded on Binance can still return zero rows for `1m`; the API must report that clearly instead of implying success.
- A partial in-progress bucket can still be aggregated for `5m`/`1h`/`1d`; this is acceptable because later real or fresher source data will overwrite aggregated rows.
- The settings table adds one small migration, but it is idempotent and isolated from the hot OHLCV path.
