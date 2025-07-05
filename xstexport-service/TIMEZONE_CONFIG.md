# Zeitzonenkonfiguration für PST/OST Kalenderdaten

## Problem
Die PST/OST-Dateien enthalten Timestamps in UTC+0, aber für die lokale Nutzung (z.B. Berlin, UTC+2) müssen diese korrekt konvertiert werden.

## Lösung
Der `DatabaseService` konvertiert automatisch alle Timestamp-Felder von UTC zur konfigurierten Zielzeitzone.

## Konfiguration

### Umgebungsvariable
Setzen Sie die Umgebungsvariable `TARGET_TIMEZONE` auf die gewünschte Zeitzone:

```bash
# Für Berlin (UTC+2 im Sommer, UTC+1 im Winter)
TARGET_TIMEZONE=Europe/Berlin

# Für andere Zeitzonen
TARGET_TIMEZONE=America/New_York
TARGET_TIMEZONE=Asia/Tokyo
TARGET_TIMEZONE=Australia/Sydney
```

### Standardwert
Falls `TARGET_TIMEZONE` nicht gesetzt ist, wird standardmäßig `Europe/Berlin` verwendet.

## Docker Compose Beispiel

```yaml
version: '3.8'
services:
  xstexport-service:
    image: xstexport-service
    environment:
      - TARGET_TIMEZONE=Europe/Berlin
      - DATABASE_URL=postgresql://user:password@db:5432/xstexport
    # ... weitere Konfiguration
```

## Betroffene Felder
Die folgenden Timestamp-Felder werden automatisch konvertiert:
- `client_submit_time`
- `start_date`
- `end_date`
- `message_delivery_time`
- `last_verb_execution_time`
- `creation_time`
- `last_modification_time`
- Alle anderen Felder mit `timestamp with time zone` Typ

## Logging
Die Zeitzonenkonvertierung wird in den Logs protokolliert:
```
INFO: Timestamp-Feld start_date von UTC zu Europe/Berlin konvertiert
INFO: Zeitzonenkonvertierung erfolgreich: UTC -> Europe/Berlin
```

## Fehlerbehandlung
Falls die Zeitzonenkonvertierung fehlschlägt, werden die ursprünglichen UTC-Timestamps verwendet und eine Warnung geloggt. 