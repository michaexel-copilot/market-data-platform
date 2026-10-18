# OHLCV-Backfill

`ohlcv_backfill.py` füllt die bestehende Tabelle `ohlcv` der Marktdaten-Datenbank mit tiefer Historie aus kostenlosen Quellen.

| Quelle (`ohlcv.source`) | Befehl | Historie |
|---|---|---|
| `okx`: OKX `history-candles` | `backfill okx` | mehrere Jahre, 100 Kerzen pro Call |
| `kraken`: Kraken OHLCVT-Dump (ZIP aus dem Kraken Support Center) | `backfill kraken --zip …` | ab erstem Trade je Paar, quartalsweise aktualisiert |

Binance Public Data ist nicht enthalten: die Binance Vision Dataset Terms v1.0 (26.08.2026) verbieten Firmen-Backtest und Firmen-Handel ausdrücklich (Klausel 4.1/4.2, siehe HED-159, Q17 — nicht freigegeben). Hyperliquid `candleSnapshot` war im ursprünglichen PR #4 enthalten, fehlt hier aber (CRO-Veto HED-154) und ist nicht Teil dieses Loaders.

Kraken ist mit der Board-Entscheidung vom 18.10.2026 freigegeben (HED-159, Q6 → D3, "freigegeben mit Auflagen"). Der **Kraken-Live-ccxt-Fallback bleibt gesperrt** (Q6b) — dieser Loader liest ausschließlich eine lokale OHLCVT-Dump-ZIP, nie einen Live-Endpunkt.

### Drei CRO-Auflagen (HED-160) für die Nutzung der vertieften Historie

Keine der drei Auflagen hält diesen Code oder seine Abnahme auf. Sie gelten für die **Nutzung** der Daten, die der Loader schreibt:

1. **Übergangsmessung an den Quellennähten.** Vor jedem S1-Ergebnis, das auf der vertieften Historie beruht, muss eine Messung an den Übergangspunkten Binance-USDT → Kraken-USD → OKX-USDT/USDC nach dem Muster von HED-131 vorliegen (Zahl, nicht Vermutung). Bis dahin muss jede Auswertung die `source`-Spalte aktiv auswerten (Filterung oder Sensitivitätsrechnung je Quellenabschnitt) — nicht nur mitführen. Verantwortlich: wer das S1-Ergebnis baut (Quant Researcher / Model Validator).
2. **Survivorship-Ausweis, getrennt.** Jedes S1-Ergebnis auf Basis der vertieften Historie muss die Kennzahlen zusätzlich für den Teilzeitraum ohne Binance/Kraken-Anteil (nur OKX) ausweisen, oder den Anteil der Equity-Kurve/Tage benennen, der auf der vertieften Vor-OKX-Historie beruht. Verantwortlich: wer das S1-Ergebnis baut.
3. **„Kein Handel" vs. „nicht geladen".** Kraken-CSV lässt Intervalle ohne Handel einfach aus, ohne Kennzeichnung. Vor Produktivbetrieb des Kraken-Pfads muss diese Unterscheidung technisch sichtbar gemacht werden (z. B. Abgleich gegen erwartete Intervalle, ähnlich den bestehenden Coverage-Views). **Dieser Loader implementiert das noch nicht** — offener Folgepunkt, Verantwortlich: Trading Systems Engineer.

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

`seed/backfill_symbols.csv` ordnet jeder `instrument_id` (wie in `instruments`) das Symbol je Börse zu. Eine leere Zelle bedeutet, dass das Instrument dort nicht geladen wird. Kontrakte mit anderem Kontraktwert (z. B. `kPEPE`) bleiben bewusst leer, weil die Preise sonst um den Faktor 1000 abweichen.

## Erstbefüllung

```bash
backfill okx --interval 1h --start 2019-01-01 --coins bitcoin   # Smoke-Test
backfill okx --interval 1h --start 2019-01-01
backfill okx --interval 1d --start 2019-01-01
backfill kraken --zip ~/Downloads/Kraken_OHLCVT.zip --intervals 1h,1d
backfill coverage > coverage.csv
```

Reihenfolge: OKX zuerst laden, danach Kraken für die Zeit davor — pro Zeitstempel wird nur eine Kerze gespeichert, wer zuerst lädt, gewinnt (`ON CONFLICT DO NOTHING`).

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
