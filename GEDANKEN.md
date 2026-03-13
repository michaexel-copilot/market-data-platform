# Initialisierung des Projekts

## Definition of Done

[x] Alle Workflow Schritte durchlaufen
[x] git commit durchgeführt

# Initialisierung der Datenbank

[x] /clear # Kontext leeren

initialize the database specified in the project. Store it on the correct place defined in .env file. write a documentation for the schema.

[ ] git commit durchgeführt

# Neues Feature: add-import-script-for-static-data-from-coinmarketcap

## Workflow

[x] /ospx-propose add-import-script-for-static-data-from-coinmarketcap

## Description

write me an import script with python for dtatic data from coinmakrtecap.
the data is stored in the folder: /mnt/ds420/data/krypto/coinmarketcap/01_download

analyze the 4 different file-patterns:
- 2026-03-12_115801_listing_data
- 2026-03-12_115801_category_data
- 2026-03-12_115801_categories_data
- 2026-03-12_115801_map_data

load the correct data into the duckdb database. extend the tables if you find valuable data that is worth storing in the db. 

write a documentation for this importer

## Definition of Done

Alle Workflow Schritte durchlaufen:
[x] /ospx-apply
[ ] /ospx-archive add-import-script-for-static-data-from-coinmarketcap

[ ] git commit durchgeführt

# Datenbankabfragen

SELECT 'cmc_categories'      AS tbl, count(*) FROM cmc_categories      UNION ALL
SELECT 'cmc_category_coins',          count(*) FROM cmc_category_coins  UNION ALL
SELECT 'cmc_coin_tags',               count(*) FROM cmc_coin_tags       UNION ALL
SELECT 'cmc_import_log',              count(*) FROM cmc_import_log      UNION ALL
SELECT 'cmc_listing_snapshots',       count(*) FROM cmc_listing_snapshots UNION ALL
SELECT 'cmc_map',                     count(*) FROM cmc_map             UNION ALL
SELECT 'instrument_crypto',           count(*) FROM instrument_crypto   UNION ALL
SELECT 'instrument_equity',           count(*) FROM instrument_equity   UNION ALL
SELECT 'instruments',                 count(*) FROM instruments         UNION ALL
SELECT 'ohlcv',                       count(*) FROM ohlcv
ORDER BY tbl;



