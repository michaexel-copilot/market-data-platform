# Postgres im LAN erreichbar machen

Stand: Postgres 16 (Ubuntu, Cluster `16-main`) lauscht nur auf `127.0.0.1:5432`. Die `DATABASE_URL` zeigt auf `localhost`. Diese Anleitung öffnet die Datenbank für das Heimnetz (`192.168.178.0/24`), ohne sie ins Internet zu stellen.

Alle Schritte brauchen `sudo`. Die Pfade sind die Ubuntu-Standardpfade und wurden nicht auf diesem Rechner geprüft (der Benutzer `market_data` darf sie nicht lesen). Vorher kontrollieren:

```bash
sudo -u postgres psql -Atc "show config_file; show hba_file;"
```

Die Datenbank `market_data_platform` und der Benutzer `market_data` stammen aus der `.env`. Rechner dieses Servers: `192.168.178.195`.

## 1. Starkes Passwort setzen

Das aktuelle Passwort ist identisch mit dem Benutzernamen. Im LAN ist das zu schwach.

```bash
NEUES_PW=$(openssl rand -base64 24 | tr -d '/+=')
echo "$NEUES_PW"          # notieren, wird nicht noch einmal angezeigt
sudo -u postgres psql -c "ALTER ROLE market_data PASSWORD '$NEUES_PW';"
```

Danach `DATABASE_URL` und `TEST_DATABASE_URL` in der `.env` anpassen (Passwort nach `market_data:` ersetzen). Das Passwort steht sonst nirgends, `.env` ist in `.gitignore`.

Hinweis: Alle Prozesse, die die alte URL benutzen (Web-App, Cron-Job für den Backfill), brauchen das neue Passwort. Die Web-App danach neu starten.

## 2. Auf der LAN-Adresse lauschen

In `/etc/postgresql/16/main/postgresql.conf`:

```
listen_addresses = 'localhost,192.168.178.195'
```

Nur diese Adresse eintragen, nicht `'*'`. Dann ist der Server nicht auf dem Docker-Interface `172.17.0.1` erreichbar.

Hat der Rechner keine feste IP, in der Fritzbox eine feste Zuweisung (DHCP-Reservierung) anlegen. Sonst bricht der Start von Postgres ab, sobald sich die Adresse ändert.

## 3. Zugriff in `pg_hba.conf` erlauben

In `/etc/postgresql/16/main/pg_hba.conf` **unter** den vorhandenen `host`-Zeilen ergänzen:

```
# LAN-Zugriff auf die Marktdaten-DB
host    market_data_platform    market_data    192.168.178.0/24    scram-sha-256
```

Damit dürfen nur dieser Benutzer und diese Datenbank aus dem Subnetz zugreifen. Die Testdatenbank (`market_data_platform_test`) bleibt lokal.

## 4. Firewall

Prüfen, ob eine läuft:

```bash
sudo ufw status
```

Ist sie aktiv, Port 5432 nur für das LAN öffnen:

```bash
sudo ufw allow from 192.168.178.0/24 to any port 5432 proto tcp
```

Ist sie nicht aktiv, entfällt dieser Schritt. Port 5432 niemals in der Fritzbox ins Internet weiterleiten (Portfreigabe).

## 5. Postgres neu starten

`listen_addresses` wirkt erst nach einem Neustart:

```bash
sudo systemctl restart postgresql@16-main
sudo systemctl status postgresql@16-main --no-pager
ss -ltn | grep 5432      # erwartet: 127.0.0.1:5432 und 192.168.178.195:5432
```

## 6. Testen

Vom Server selbst, über die LAN-Adresse:

```bash
psql "postgresql://market_data:NEUES_PW@192.168.178.195/market_data_platform" -c "select count(*) from ohlcv;"
```

Von einem anderen Rechner im LAN:

```bash
psql "postgresql://market_data:NEUES_PW@192.168.178.195:5432/market_data_platform" -c "select 1;"
```

Kommt "Connection refused", fehlt Schritt 2 oder 5. Kommt ein Timeout, blockt die Firewall (Schritt 4). Kommt "no pg_hba.conf entry", fehlt oder stimmt Schritt 3 nicht (nach einer Änderung an `pg_hba.conf` reicht `sudo systemctl reload postgresql@16-main`).

## 7. Clients im LAN

```
DATABASE_URL=postgresql://market_data:NEUES_PW@192.168.178.195:5432/market_data_platform
```

Der Benutzer `market_data` hat Schreibrechte auf `ohlcv`. Soll ein Rechner nur lesen (etwa für Auswertungen), besser eine eigene Rolle anlegen:

```sql
CREATE ROLE market_reader LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE market_data_platform TO market_reader;
GRANT USAGE ON SCHEMA public TO market_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO market_reader;
```

und deren Namen in Schritt 3 statt `market_data` eintragen (zusätzliche Zeile).

## Rückgängig machen

Zeile in `pg_hba.conf` löschen, `listen_addresses = 'localhost'` setzen, die ufw-Regel entfernen (`sudo ufw delete allow from 192.168.178.0/24 to any port 5432 proto tcp`) und Postgres neu starten.

## Sicherheit

- Postgres sendet ohne TLS. Im Heimnetz ist das üblich, über WLAN fremder Netze oder VPN-Strecken aber nicht. Dann `ssl = on` konfigurieren und `hostssl` statt `host` in `pg_hba.conf` verwenden, oder einen SSH-Tunnel nutzen: `ssh -L 5432:localhost:5432 michael@192.168.178.195`. Der Tunnel kommt ohne alle Änderungen oben aus.
- Der Backfill-Loader schreibt in `ohlcv`. Läuft er auf mehreren Rechnern gleichzeitig, entstehen keine Duplikate (`ON CONFLICT DO NOTHING`), aber doppelte API-Aufrufe.
