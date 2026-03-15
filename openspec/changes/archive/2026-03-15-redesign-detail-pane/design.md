## Context

The detail pane (`templates/asset_detail.html`) currently uses a four-button tab group rendered inside the HTMX partial. Switching tabs triggers a full `GET /asset/{symbol}` reload of the entire partial, passing the desired `tab` query parameter. The server renders one of four `{% if tab == ... %}` branches and returns HTML rooted at the detail pane.

The template is ~1 100 lines and already depends on Bootstrap 5 (loaded in the base layout). Jinja2 and HTMX are the only rendering primitives available — no build step, no React/Vue.

## Goals / Non-Goals

**Goals:**
- Replace the tab-bar with a Bootstrap 5 accordion (six panels) rendered in a single pass.
- Keep all six content sections addressable/visible on one scroll without full-page reloads.
- Preserve all existing HTMX-triggered interactions (SMA spinner changes, Find Best SMA, trade-row highlight, performance-chart resolution toggle).
- Keep the server-side route and data model unchanged.

**Non-Goals:**
- Persisting accordion open/closed state across page loads or asset switches.
- Lazy-loading accordion panel content (all panels are rendered server-side in one response).
- Adding animation or custom accordion styling beyond Bootstrap defaults.
- Refactoring `web.py` beyond removing the `tab` branch (the `tab` parameter can be retained for backward-compat or silently ignored).

## Decisions

### Decision 1 — Bootstrap `accordion` component, not custom JS

**Choice:** Use Bootstrap 5's built-in `accordion` / `collapse` classes and `data-bs-toggle` attributes.

**Rationale:** Bootstrap is already loaded; no new JS dependency. The accordion works with `data-bs-parent` for mutual-exclusion or without it for independent panels. We use **independent panels** (no `data-bs-parent`) so the user can have e.g. Chart and Strategy Controls open simultaneously.

**Alternative considered:** Plain `<details>/<summary>` HTML elements. Rejected because they don't match the Bootstrap visual language already used on the page, and adding transitions would require extra CSS.

### Decision 2 — All content rendered server-side in one response

**Choice:** The server renders all six accordion panels unconditionally in a single HTMX partial response.

**Rationale:** Keeps the current single-route architecture. No lazy-fetch per panel means no additional round-trips when opening a collapsed panel. The chart image and performance chart are already generated at request time, so there is no cost saving from lazy rendering.

**Alternative considered:** Each panel fetches its content via `hx-get` on `show.bs.collapse`. Rejected: adds complexity, requires six new server endpoints or a panel-type query parameter, and delays panel content on every open.

### Decision 3 — Remove `tab` routing from the template; keep hidden inputs

**Choice:** Delete the four `{% if tab == "..." %}` branches and the tab-button-group. Keep all `<input type="hidden">` elements that carry HTMX state (sma, sma_high, sl_short, sl_long, pos, resolution, highlight, hl_long).

**Rationale:** The hidden inputs are used by `hx-include` on SMA spinners and trade-row clicks. They continue to work regardless of tab structure. Only the visible tab selector and conditional rendering blocks are removed.

**Alternative considered:** Converting hidden inputs to Session storage / URL params. Out of scope.

### Decision 4 — Default panel states

| Panel | Default | Rationale |
|---|---|---|
| 1 Fundamentals | **open** | Quick reference on first load |
| 2 Chart | **closed** | Large image; user opens on demand |
| 3 Strategy Controls | **open** | Core workflow; visible immediately |
| 4 Trades Table | **closed** | Long scrollable table; opened when needed |
| 5 Performance | **closed** | Secondary analysis |
| 6 Place Order | **closed** | Destructive action; should not be open by default |

## Risks / Trade-offs

- **Chart scroll position**: With all panels in one page, the chart may be off-screen unless the user scrolls. Mitigation: Strategy Controls (expanded) are above the chart, so the chart panel collapse button is immediately accessible.
- **Hidden-input ID collisions**: Previously some hidden inputs were duplicated across tab branches (one per `{% elif %}`). After merging into a single flow, each `id` must appear exactly once. Mitigation: audit all `id=` attributes during implementation and remove duplicates.
- **Performance chart canvas**: The lightweight-charts `<div id="perf-chart">` is rendered in a collapsed panel. `clientWidth` will be `0` when collapsed. Mitigation: the existing `requestAnimationFrame` + `ResizeObserver` pattern already handles this — it fires when the panel is expanded and the container becomes visible.
- **`tab` parameter from bookmarks / external links**: Existing links with `?tab=...` will no longer drive visible tab state. Mitigation: the parameter can be accepted and used to set `data-bs-toggle` `show` class server-side on the matching panel, but this is an enhancement; base implementation can ignore it.

## Migration Plan

1. Edit `templates/asset_detail.html`:
   a. Remove the tab-button-group `<div class="btn-group ...">`.
   b. Remove the four `{% if tab == ... %} ... {% elif %} ... {% endif %}` blocks.
   c. Wrap each former tab's content in a `.accordion-item` / `.accordion-header` / `.accordion-collapse` structure.
   d. Set `show` class on panels 1 (Fundamentals) and 3 (Strategy Controls) by default.
   e. Consolidate duplicate hidden inputs to a single set at the top of the partial.

2. `web.py`: the `tab` query param can remain or be removed. No logic change required.

3. Manual smoke test: load the app, click each accordion header, trigger SMA spinner change, click a trade row, open Performance chart, toggle resolution, open Place Order.

**Rollback:** `git revert` or `git checkout HEAD templates/asset_detail.html`.

## Open Questions

- Should the `tab` parameter be honoured to pre-open a specific panel (e.g. for direct links)? → Deferred; not in scope for this change.
