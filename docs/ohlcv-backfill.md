# OHLCV-Backfill

`ohlcv_backfill.py` füllt die TimescaleDB mit tiefer Historie aus kostenlosen Quellen.

| Quelle | Befehl | Historie |
|---|---|---|
| Binance Public Data (data.binance.vision) | `backfill binance` | ab Listing (BTCUSDT ab 08/2017), Spot oder USDⓈ-M-Futures |
| Kraken OHLCVT-Dump (ZIP aus dem Kraken Support Center) | `backfill kraken --zip …` | ab erstem Trade je Paar, quartalsweise aktualisiert |
| OKX `history-candles` | `backfill okx` | mehrere Jahre, 100 Kerzen pro Call |
| Hyperliquid `candleSnapshot` | `backfill hyperliquid` | nur die letzten 5000 Kerzen, deshalb täglich `update` laufen lassen |

## Einrichtung

```bash
export DATABASE_URL=postgresql://user:pass@host:5432/marketdata
export OHLCV_TABLE=ohlcv          # optional, Standard "ohlcv"
uv run backfill init-schema       # Tabelle, Unique-Index, Compression, Views (idempotent)
```

`db/ohlcv_schema.sql` legt an:

- die Hypertable `(coin, interval, source, ts, open, high, low, close, volume, trade_count, vwap, is_aggregated)` mit Unique-Index auf `(coin, interval, source, ts)`. Bestehende Zeilen werden nie überschrieben.
- `ohlcv_coverage`: Tiefe, Füllgrad und Rückstand je Serie (ersetzt die Excel-Übersicht).
- `ohlcv_gaps`: jede Lücke innerhalb einer Serie.
- `ohlcv_1d_from_1h`: Continuous Aggregate, das Tageskerzen aus 1h-Kerzen bildet.

Existiert die Tabelle bereits mit anderen Spaltennamen, überspringt `CREATE TABLE` sie, und Index bzw. Views schlagen mit einer klaren Fehlermeldung fehl. In dem Fall die Namen in der SQL-Datei anpassen.

## Welche Coins

`seed/backfill_symbols.csv` ordnet jedem Coin-Slug (wie in der DB, z. B. `bitcoin`) das Symbol je Börse zu. Eine leere Zelle bedeutet, dass der Coin dort nicht geladen wird. Paare mit anderem Kontraktwert (z. B. `1000PEPEUSDT`, `kPEPE`) bleiben bewusst leer, weil die Preise sonst um den Faktor 1000 abweichen.

## Erstbefüllung

```bash
uv run backfill binance --interval 1h --start 2017-08
uv run backfill binance --interval 1d --start 2017-08
uv run backfill binance --interval 1m --start 2024-01 --coins bitcoin,ethereum
uv run backfill kraken --zip ~/Downloads/Kraken_OHLCVT.zip --intervals 1h,1d
uv run backfill okx --interval 1h --start 2019-01-01 --coins bitcoin
uv run backfill hyperliquid --interval 1h
uv run backfill coverage > coverage.csv
```

## Täglicher Lauf (Cron)

```cron
15 2 * * *  cd /app && uv run backfill update --days 3 --intervals 1h,1d
```

`update` lädt die letzten N Tage aus Binance (tägliche ZIPs, ein Tag Verzögerung), OKX und Hyperliquid.

## Tests

```bash
uv run --with pytest pytest tests/test_ohlcv_backfill.py
# mit echter TimescaleDB:
docker run -d -e POSTGRES_PASSWORD=pw -p 55432:5432 timescale/timescaledb:latest-pg16
TEST_DATABASE_URL=postgresql://postgres:pw@127.0.0.1:55432/postgres uv run --with pytest pytest tests/
```
