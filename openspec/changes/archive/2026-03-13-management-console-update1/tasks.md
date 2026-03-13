## 1. Database Migrations

- [x] 1.1 Create migration `012_data_source.sql` — `data_source` table with columns: `data_source_id` SEQUENCE PK, `name`, `short_name`, `base_url`, `api_page_url` (nullable), `retrieval_priority` (nullable INTEGER)
- [x] 1.2 Create migration `013_attribute_source_map.sql` — `attribute_source_map` table with PK `(instrument_id, attribute_name)`, FK to `instruments` and FK to `data_source`
- [x] 1.3 Create migration `014_ticker_source_map.sql` — `ticker_source_map` table with PK `(instrument_id, data_source_id)`, FK to `instruments` and `data_source`, `source_ticker` VARCHAR, `is_canonical` BOOLEAN DEFAULT FALSE
- [x] 1.4 Seed `data_source` with the CoinMarketCap entry (name=`CoinMarketCap`, short_name=`cmc`, base_url=`https://coinmarketcap.com`, api_page_url=`https://coinmarketcap.com/api`, retrieval_priority=`0`) in the migration file

## 2. Migration Logic (Backend)

- [x] 2.1 Create `src/market_data/ingestion/migrate_fundamentals.py` with a `migrate_fundamentals(conn)` function that: (a) resolves the CoinMarketCap `data_source_id`, (b) for each matched instrument/CMC listing row promotes `full_name`, `total_supply`, `max_supply`, `circulating_supply`, `cmc_rank`, `cmc_slug`, `cmc_id` into canonical tables, (c) upserts `attribute_source_map` rows for each promoted attribute, (d) upserts `ticker_source_map` with `source_ticker = cmc_symbol`, (e) returns `{promoted: N, skipped: N, errors: [...]}`
- [x] 2.2 Match CMC listing to instruments using `cmc_listing_snapshots.symbol` ↔ `instruments.ticker` (scoped to `asset_class='crypto'`); use the latest snapshot timestamp

## 3. REST Endpoint

- [x] 3.1 Add `POST /v1/admin/migrate-fundamentals` route in `src/market_data/api/rest/app.py` (or a new `admin.py` router) that calls `migrate_fundamentals(conn)` and returns `{"promoted": N, "skipped": N, "errors": [...]}`

## 4. Console UI

- [x] 4.1 Add `#ACT_BTN_LIST` flex container to the top bar in `console.py`, right-aligned (use `margin-left: auto` or flex spacer), as sibling of `#SEG_ASSET_CLASS`
- [x] 4.2 Add `#BTN_MIGRATE_FUNDAMENTALS` button inside `#ACT_BTN_LIST` with label "Migrate Fundamental Data"; always enabled
- [x] 4.3 Wire `BTN_MIGRATE_FUNDAMENTALS` click: call `POST /v1/admin/migrate-fundamentals`, on success reload instrument list and show success message in fundamentals pane, on error show error message in fundamentals pane
- [x] 4.4 Wire instrument list item click to call `GET /v1/instruments/{id}/fundamentals` and render the result as a label-value table in `PANE_FUNDAMENTALS` (this is already stubbed — make it functional after migration data is available)
