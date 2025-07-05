# Zeitzonenkonfiguration für PST/OST Kalenderdaten

## Problem
Die PST/OST-Dateien enthalten Timestamps in UTC+0, aber für die lokale Nutzung (z.B. Berlin, UTC+2) müssen diese korrekt konvertiert werden.

## Lösung
Der `DatabaseService` konvertiert automatisch alle Timestamp-Felder von UTC zur konfigurierten Zielzeitzone und speichert sie als naive datetime-Objekte in der Datenbank.

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

## Funktionsweise

### 1. Zeitzonenkonvertierung
- UTC-Timestamps werden zur Zielzeitzone konvertiert
- Sommer-/Winterzeit wird automatisch berücksichtigt
- Beispiel: `2023-10-12 16:07:08Z` → `2023-10-12 18:07:08` (Berlin Sommerzeit)

### 2. SQLAlchemy-Kompatibilität
- Zeitzoneninformationen werden entfernt, aber konvertierte Werte beibehalten
- Naive datetime-Objekte werden in der Datenbank gespeichert
- SQLAlchemy kann die Werte korrekt verarbeiten

### 3. Fallback-Mechanismus
- Falls pandas-Zeitzonenkonvertierung fehlschlägt, wird manuelle Konvertierung verwendet
- Für Berlin: +2 Stunden werden addiert

## Logging
Die Zeitzonenkonvertierung wird in den Logs protokolliert:
```
INFO: Timestamp-Feld start_date von UTC zu Europe/Berlin konvertiert
INFO: Zeitzonenkonvertierung erfolgreich: UTC -> Europe/Berlin (naive)
```

## Fehlerbehandlung
Falls die Zeitzonenkonvertierung fehlschlägt, werden die ursprünglichen UTC-Timestamps verwendet und eine Warnung geloggt.

## Debug-Endpoints

### Zeitzonenkonvertierung testen
```bash
curl -X POST 'http://localhost:8200/debug-timezone-conversion' \
-F 'file=@calendar.csv'
```

### Vollständigen Import testen
```bash
curl -X POST 'http://localhost:8200/test-import-with-debug' \
-F 'file=@calendar.csv'
```

## Beispiel-Konvertierung

| Original (UTC) | Konvertiert (Berlin) | Bemerkung |
|---|---|---|
| `2023-10-12 16:07:08Z` | `2023-10-12 18:07:08` | Sommerzeit (+2h) |
| `2023-12-02 23:00:00Z` | `2023-12-03 00:00:00` | Winterzeit (+1h) |
| `2023-11-02 11:28:41Z` | `2023-11-02 12:28:41` | Winterzeit (+1h) | 