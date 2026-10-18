# OHLCV-Backfill

`ohlcv_backfill.py` füllt die bestehende Tabelle `ohlcv` der Marktdaten-Datenbank mit tiefer Historie aus kostenlosen Quellen.

| Quelle (`ohlcv.source`) | Befehl | Historie |
|---|---|---|
| `okx`: OKX `history-candles` | `backfill okx` | mehrere Jahre, 100 Kerzen pro Call |

Binance Public Data ist nicht enthalten: die Binance Vision Dataset Terms v1.0 (26.08.2026) verbieten Firmen-Backtest und Firmen-Handel ausdrücklich (Klausel 4.1/4.2, siehe HED-159). Der Kraken-OHLCVT-Dump und Hyperliquid `candleSnapshot` waren im ursprünglichen PR #4 enthalten, fehlen hier aber, bis das Board die Katalogänderung (HED-159/HED-10) entschieden hat. Sie können in einer eigenen Folge-PR nachgezogen werden, sobald das vorliegt.

## So schreibt der Loader

- Kerzen landen über den Primärschlüssel `(instrument_id, interval, ts)` mit `ON CONFLICT DO NOTHING` in `ohlcv`. Eine vorhandene Kerze wird nie überschrieben, egal aus welcher Quelle sie stammt. Der Loader füllt nur Lücken und verlängert die Historie.
- `tick_1m`, `tick_1h` und `tick_1d` werden aus `ts` berechnet (`epoch // 60`, `// 3600`, `// 86400`).
- Kerzen, die den Check `ohlcv_price_sanity` verletzen würden, werden übersprungen und gezählt. Sonst würde eine einzige fehlerhafte Kerze den ganzen Batch abbrechen.
- Nur die Intervalle `1m`, `5m`, `1h` und `1d` werden geladen (`ohlcv_interval_check`).
- Nach dem Laden wird in `ohlcv_data_available` `has_<interval>` für den passenden `data_source`-Eintrag gesetzt, falls einer existiert. OKX hat noch keinen `data_source`-Eintrag und wird deshalb nicht markiert.
- Eine `instrument_id`, die nicht in `instruments` existiert, wird mit einem Hinweis übersprungen.

## Einrichtung

```bash
git checkout <branch>
export DATABASE_URL=postgresql://USER:PASSWORT@HOST:5432/DBNAME
alias backfill='uv run --no-project --with requests --with "psycopg[binary]" python ohlcv_backfill.py'
backfill init-views        # legt nur die Views backfill_coverage und backfill_gaps an
```

`init-views` ändert nichts an `ohlcv`, sondern legt nur zwei lesende Views an:

- `backfill_coverage`: Tiefe, Füllgrad und Rückstand je Instrument, Intervall und Quelle (ersetzt die Excel-Übersicht).
- `backfill_gaps`: jede Lücke innerhalb einer Serie. Beim Abfragen nach `instrument_id` filtern.

## Welche Instrumente

`seed/backfill_symbols.csv` ordnet jeder `instrument_id` (wie in `instruments`) das OKX-Symbol zu. Eine leere Zelle bedeutet, dass das Instrument dort nicht geladen wird. Kontrakte mit anderem Kontraktwert (z. B. `kPEPE`) bleiben bewusst leer, weil die Preise sonst um den Faktor 1000 abweichen.

## Erstbefüllung

```bash
backfill okx --interval 1h --start 2019-01-01 --coins bitcoin   # Smoke-Test
backfill okx --interval 1h --start 2019-01-01
backfill okx --interval 1d --start 2019-01-01
backfill coverage > coverage.csv
```

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
```
