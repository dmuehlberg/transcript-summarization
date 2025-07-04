# Zeitzonenunterstützung für Kalenderdaten

## Übersicht

Das System unterstützt jetzt automatische Zeitzonenkonvertierung für Kalenderdaten. PST-Dateien enthalten UTC+0 Daten, die automatisch zur konfigurierten lokalen Zeitzone konvertiert werden.

## Konfiguration

### .env-Datei

Fügen Sie in der `.env`-Datei im Projekt-Root folgende Zeile hinzu:

```bash
# Zeitzonenkonfiguration für Kalenderdaten
# Mögliche Werte: UTC, Europe/Berlin, America/New_York, etc.
# Standard: UTC+2 (Berlin)
TIMEZONE=Europe/Berlin

# Alternative: UTC (falls keine Zeitzonenkonvertierung gewünscht)
# TIMEZONE=UTC
```

### Unterstützte Zeitzonen

Alle von `pytz` unterstützten Zeitzonen sind verfügbar:

- `Europe/Berlin` (UTC+1/+2 mit Sommerzeit)
- `Europe/London` (UTC+0/+1 mit Sommerzeit)
- `America/New_York` (UTC-5/-4 mit Sommerzeit)
- `Asia/Tokyo` (UTC+9)
- `UTC` (keine Konvertierung)

## Funktionsweise

### 1. PST-Dateien (UTC+0 → Lokale Zeit)

PST-Dateien enthalten Kalenderdaten in UTC+0. Das System:

1. **Liest UTC-Daten** aus PST-Dateien
2. **Konvertiert automatisch** zur konfigurierten Zeitzone
3. **Speichert als lokale Zeit** in der Datenbank

**Beispiel:**
- PST-Daten: `2025-01-15 14:00:00` (UTC)
- Konfiguration: `TIMEZONE=Europe/Berlin`
- Ergebnis: `2025-01-15 15:00:00` (Berlin-Zeit, Winter) oder `2025-01-15 16:00:00` (Berlin-Zeit, Sommer)

### 2. macOS-Kalender (Bereits lokale Zeit)

macOS-Kalenderdaten sind bereits in lokaler Zeit:

1. **Liest deutsche Datumsstrings** (z.B. "Montag, 23. Juni 2025 um 14:00:00")
2. **Konvertiert zur konfigurierten Zeitzone** (falls anders als Berlin)
3. **Speichert in der Datenbank**

### 3. Datenbank-Speicherung

Alle Timestamps werden als `TIMESTAMP` (ohne Zeitzone) gespeichert:
- Einfache Abfragen ohne Zeitzonenkonvertierung
- Konsistente lokale Zeit in der gesamten Anwendung

## Implementierung

### Neue Dateien

1. **`xstexport-service/app/utils/timezone_utils.py`**
   - Zeitzonenkonvertierungsfunktionen
   - Unterstützung für verschiedene Timestamp-Formate

2. **`.env`** (im Projekt-Root)
   - Zeitzonenkonfiguration

### Geänderte Dateien

1. **`xstexport-service/app/services/db_service.py`**
   - Automatische Zeitzonenkonvertierung beim CSV-Import
   - Zeitzonenkonvertierung für macOS-Kalenderdaten

2. **`xstexport-service/app/services/mac_calendar_service.py`**
   - Zeitzonenkonvertierung für deutsche Datumsstrings

3. **`xstexport-service/requirements.txt`**
   - Hinzugefügt: `pytz` für Zeitzonenunterstützung

## Verwendung

### Automatische Konvertierung

Die Zeitzonenkonvertierung erfolgt automatisch bei:

1. **PST/OST-Import** über `/extract-calendar-from-file`
2. **macOS-Kalender-Import** über `/mac/export-calendar`
3. **CSV-Import** über `db_service.import_csv_to_db()`

### Manuelle Konvertierung

```python
from app.utils.timezone_utils import convert_utc_to_local, parse_and_convert_timestamp

# UTC zu lokaler Zeit
utc_time = "2025-01-15 14:00:00"
local_time = convert_utc_to_local(utc_time, 'UTC')

# Timestamp-String parsen und konvertieren
timestamp_str = "2025-01-15T14:00:00Z"
local_time = parse_and_convert_timestamp(timestamp_str, 'UTC')
```

## Konfigurationsbeispiele

### Berlin (UTC+1/+2)
```bash
TIMEZONE=Europe/Berlin
```
- Winter: UTC+1
- Sommer: UTC+2 (Sommerzeit)

### London (UTC+0/+1)
```bash
TIMEZONE=Europe/London
```
- Winter: UTC+0
- Sommer: UTC+1 (Sommerzeit)

### New York (UTC-5/-4)
```bash
TIMEZONE=America/New_York
```
- Winter: UTC-5
- Sommer: UTC-4 (Sommerzeit)

### Keine Konvertierung
```bash
TIMEZONE=UTC
```
- Alle Daten bleiben in UTC

## Testing

### Zeitzonenkonvertierung testen

1. **PST-Datei importieren** mit verschiedenen TIMEZONE-Einstellungen
2. **Meeting-Zuordnung prüfen** über `/get_meeting_info`
3. **Datenbankabfragen** zur Verifikation der korrekten Zeiten

### Beispiel-Test

```bash
# 1. Zeitzone auf Berlin setzen
echo "TIMEZONE=Europe/Berlin" >> .env

# 2. PST-Datei importieren
curl -X POST "http://localhost:8000/extract-calendar-from-file" \
  -F "file=@calendar.pst" \
  -F "import_to_db=true"

# 3. Meeting-Info abrufen
curl -X POST "http://localhost:8000/get_meeting_info" \
  -H "Content-Type: application/json" \
  -d '{"recording_date": "2025-01-15 15-00"}'
```

## Vorteile

1. **Automatische Konvertierung**: Keine manuelle Zeitzonenberechnung nötig
2. **Flexible Konfiguration**: Einfache Anpassung über .env-Datei
3. **Konsistente Daten**: Alle Timestamps in lokaler Zeit
4. **Sommerzeit-Unterstützung**: Automatische Behandlung von DST
5. **Einfache Abfragen**: Keine Zeitzonenkonvertierung bei Datenbankabfragen

## Troubleshooting

### Häufige Probleme

1. **Falsche Zeitzone**: Prüfen Sie die TIMEZONE-Einstellung in .env
2. **Import-Fehler**: Stellen Sie sicher, dass pytz installiert ist
3. **Sommerzeit-Probleme**: Verwenden Sie vollständige Zeitzonennamen (z.B. `Europe/Berlin` statt `UTC+2`)

### Debugging

Aktivieren Sie Debug-Logging für Zeitzonenkonvertierung:

```python
import logging
logging.getLogger('app.utils.timezone_utils').setLevel(logging.DEBUG)
``` 