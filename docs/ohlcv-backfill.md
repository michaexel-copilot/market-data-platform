# OHLCV-Backfill

`ohlcv_backfill.py` füllt die bestehende Tabelle `ohlcv` der Marktdaten-Datenbank mit tiefer Historie aus kostenlosen Quellen.

| Quelle (`ohlcv.source`) | Befehl | Historie |
|---|---|---|
| `binance`: Binance Public Data, Spot (data.binance.vision) | `backfill binance` | ab Listing (BTCUSDT ab 08/2017) |
| `kraken`: Kraken OHLCVT-Dump (ZIP aus dem Kraken Support Center) | `backfill kraken --zip …` | ab erstem Trade je Paar, quartalsweise aktualisiert |
| `okx`: OKX `history-candles` | `backfill okx` | mehrere Jahre, 100 Kerzen pro Call |
| `hyperliquid`: Hyperliquid `candleSnapshot` | `backfill hyperliquid` | nur die letzten 5000 Kerzen, deshalb täglich `update` laufen lassen |

## So schreibt der Loader

- Kerzen landen über den Primärschlüssel `(instrument_id, interval, ts)` mit `ON CONFLICT DO NOTHING` in `ohlcv`. Eine vorhandene Kerze wird nie überschrieben, egal aus welcher Quelle sie stammt. Der Loader füllt nur Lücken und verlängert die Historie.
- `tick_1m`, `tick_1h` und `tick_1d` werden aus `ts` berechnet (`epoch // 60`, `// 3600`, `// 86400`).
- Kerzen, die den Check `ohlcv_price_sanity` verletzen würden, werden übersprungen und gezählt. Sonst würde eine einzige fehlerhafte Kerze den ganzen Batch abbrechen.
- Nur die Intervalle `1m`, `5m`, `1h` und `1d` werden geladen (`ohlcv_interval_check`).
- Nach dem Laden wird in `ohlcv_data_available` `has_<interval>` für den passenden `data_source`-Eintrag gesetzt: `binance_hist`, `kraken_hist` und `hl`. OKX hat noch keinen `data_source`-Eintrag und wird deshalb nicht markiert.
- Eine `instrument_id`, die nicht in `instruments` existiert, wird mit einem Hinweis übersprungen.

## Einrichtung

```bash
git checkout ohlcv-backfill-loader
export DATABASE_URL=postgresql://USER:PASSWORT@HOST:5432/DBNAME
alias backfill='uv run --no-project --with requests --with "psycopg[binary]" python ohlcv_backfill.py'
backfill init-views        # legt nur die Views backfill_coverage und backfill_gaps an
```

`init-views` ändert nichts an `ohlcv`, sondern legt nur zwei lesende Views an:

- `backfill_coverage`: Tiefe, Füllgrad und Rückstand je Instrument, Intervall und Quelle (ersetzt die Excel-Übersicht).
- `backfill_gaps`: jede Lücke innerhalb einer Serie. Beim Abfragen nach `instrument_id` filtern.

## Welche Instrumente

`seed/backfill_symbols.csv` ordnet jeder `instrument_id` (wie in `instruments`) das Symbol je Börse zu. Eine leere Zelle bedeutet, dass das Instrument dort nicht geladen wird. Kontrakte mit anderem Kontraktwert (z. B. `kPEPE`) bleiben bewusst leer, weil die Preise sonst um den Faktor 1000 abweichen.

## Erstbefüllung

```bash
backfill binance --coins bitcoin --interval 1d --start 2026-01   # Smoke-Test
backfill binance --interval 1h --start 2017-08
backfill binance --interval 1d --start 2017-08
backfill kraken --zip ~/Downloads/Kraken_OHLCVT.zip --intervals 1h,1d
backfill okx --interval 1h --start 2019-01-01 --coins bitcoin
backfill hyperliquid --interval 1h
backfill coverage > coverage.csv
```

Die Reihenfolge ist wichtig, weil pro Zeitstempel nur eine Kerze gespeichert wird: Wer zuerst lädt, gewinnt. Binance (USDT) zuerst, danach Kraken (USD) für die Zeit vor Binance.

## Täglicher Lauf (Cron)

```cron
15 2 * * *  cd /pfad/market-data-platform && DATABASE_URL=... uv run --no-project --with requests --with "psycopg[binary]" python ohlcv_backfill.py update --days 3 --intervals 1h,1d
```

## Tests

```bash
uv run --with pytest pytest tests/test_ohlcv_backfill.py
# mit echter TimescaleDB (die Tests legen eine eigene Datenbank backfill_test an):
docker run -d -e POSTGRES_PASSWORD=pw -p 55432:5432 timescale/timescaledb:latest-pg16
TEST_DATABASE_URL=postgresql://postgres:pw@127.0.0.1:55432/postgres uv run --with pytest pytest tests/
