## 1. Table Heading

- [x] 1.1 Add "Cached Backtests" heading above the table (and above the empty-state message) in `templates/backtest_history.html`

## 2. Sortable Columns

- [x] 2.1 Add `data-col` and `style="cursor:pointer"` attributes to each sortable `<th>` in the table header
- [x] 2.2 Implement `sortTable(th)` vanilla-JS function: determine column index and data type (numeric vs string), sort `<tbody>` rows, toggle asc/desc state, update sort indicator (▲/▼) on the header
- [x] 2.3 Wire `onclick="sortTable(this)"` to each sortable `<th>`
