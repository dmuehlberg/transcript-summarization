# XST Export Service

Ein FastAPI-Service zum Extrahieren und Importieren von Kalenderdaten aus PST/OST/ZIP-Dateien.

## Endpoints

### 1. Kalender-Extraktion

#### POST `/extract-calendar/`
Extrahiert Kalenderdaten aus PST/OST-Dateien.

**Parameter:**
- `file`: PST/OST-Datei (UploadFile)
- `format`: Format der Extraktion ('csv' oder 'native', Standard: 'csv')
- `target_folder`: Optionaler Zielordner
- `return_file`: Ob die ZIP-Datei als Download zurückgegeben werden soll (Standard: false)
- `pst_folder`: Name des Ordners in der PST-Datei (Standard: "Calendar")
- `extract_all`: Ob alle Elemente extrahiert werden sollen (Standard: false)

#### POST `/extract-calendar-from-file`
Extrahiert Kalenderdaten aus hochgeladenen Dateien (ZIP, PST, OST).

**Parameter:**
- `file`: Die zu verarbeitende Datei (ZIP, PST oder OST)
- `format`: Format der Extraktion ('csv' oder 'native', Standard: 'csv')
- `extract_all`: Ob alle Elemente extrahiert werden sollen (Standard: false)
- `return_file`: Ob die ZIP-Datei als Download zurückgegeben werden soll (Standard: false)
- `import_to_db`: Ob die Daten in die Datenbank importiert werden sollen (Standard: false)

### 2. CSV-Import (NEU)

#### POST `/import-calendar-csv`
Importiert Kalenderdaten direkt aus einer CSV-Datei in die Datenbank.

**Parameter:**
- `file`: Die hochgeladene CSV-Datei (UploadFile)
- `table_name`: Name der Zieltabelle in der Datenbank (Standard: "calendar_data")

**Beispiel curl-Befehl:**
```bash
curl -X POST "http://localhost:8000/import-calendar-csv" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@calendar_data.csv" \
  -F "table_name=calendar_data"
```

**Antwort:**
```json
{
  "status": "success",
  "message": "CSV-Datei erfolgreich in Tabelle 'calendar_data' importiert",
  "table_name": "calendar_data",
  "filename": "calendar_data.csv"
}
```

### 3. PST/OST-Ordner-Verwaltung

#### POST `/list-pst-folders`
Listet alle Ordner in einer PST/OST-Datei auf.

**Body-Parameter:**
- `filename`: Name der Datei im /data/ost-Verzeichnis

### 4. System-Endpoints

#### GET `/health`
Überprüft die Anwendungsverfügbarkeit.

#### GET `/debug/files`
Zeigt den Inhalt des Anwendungsverzeichnisses für Debugging-Zwecke an.

#### GET `/data/files`
Zeigt den Inhalt des Datenverzeichnisses für Debugging-Zwecke an.

#### GET `/debug/dotnet`
Testet die .NET-Laufzeit und gibt Debug-Informationen zurück.

## Datenbank-Integration

Der Service unterstützt die direkte Integration in eine PostgreSQL-Datenbank:

- Automatische Tabellenerstellung basierend auf dem Mapping in `config/calendar_mapping.json`
- Sichere CSV-Einlesung mit Unterstützung für verschiedene Trennzeichen (Semikolon, Komma)
- Datentyp-Konvertierung für Timestamps, Integer und Boolean-Werte
- Zeitzonen-Behandlung (UTC-Konvertierung)

## Installation und Start

1. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

2. Service starten:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker

```bash
docker-compose up -d
```

## Fehlerbehandlung

Alle Endpoints implementieren umfassende Fehlerbehandlung:
- Validierung der Eingabedateien
- Temporäre Dateiverwaltung mit automatischer Bereinigung
- Detaillierte Logging-Ausgaben
- HTTP-Statuscodes für verschiedene Fehlertypen

## Testing

Ein einfacher Test für den neuen CSV-Import-Endpoint ist verfügbar:

```bash
python test_csv_import.py
```

Der Test erstellt eine Test-CSV-Datei und sendet sie an den `/import-calendar-csv` Endpoint. Stellen Sie sicher, dass der Service läuft, bevor Sie den Test ausführen. 