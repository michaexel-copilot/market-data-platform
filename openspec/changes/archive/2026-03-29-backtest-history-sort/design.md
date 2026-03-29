## Context

The backtest history table (`templates/backtest_history.html`) is a plain Bootstrap table rendered as an HTMX partial. It currently has no label and static column order. Users want to sort runs by P&L, number of trades, etc. The app uses no external JS charting/table libraries beyond Bootstrap 5 and HTMX.

## Goals / Non-Goals

**Goals:**
- Add a "Cached Backtests" heading above the table
- Sortable columns via vanilla JS (click header toggles asc/desc)
- Visual sort indicator on the active column header
- No new dependencies

**Non-Goals:**
- Server-side sorting
- Pagination or filtering
- Persisting sort state across page loads

## Decisions

**Vanilla JS sort, no library** — The table is a small HTMX partial. Adding a dependency (e.g. DataTables) would require CDN changes and conflict with HTMX swap lifecycle. A ~30-line inline sort function is sufficient and zero-cost.

**Sort in-place by reordering `<tr>` nodes** — Avoids re-fetching from server; works entirely in the DOM after the partial loads. Triggered by `click` on `<th>` elements.

**Data types inferred from column index** — Numeric columns (P&L, trade count) parsed with `parseFloat`; string columns fall back to locale compare.

## Risks / Trade-offs

[Risk] Sort state resets on HTMX refresh (after new backtest run) → Acceptable; the table is small and the user can re-sort with one click.
