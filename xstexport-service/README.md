# XSTExport Service

Ein FastAPI-basierter Service zur Extraktion von Kalenderdaten aus PST/OST-Dateien und Import von CSV-Daten in eine PostgreSQL-Datenbank.

## Features

- Extraktion von Kalenderdaten aus PST/OST-Dateien
- Unterstützung für ZIP-Archive mit PST/OST-Dateien
- Direkter Import von CSV-Dateien in die Datenbank
- PostgreSQL-Integration mit automatischem Schema-Mapping
- CORS-Unterstützung für Cross-Origin-Anfragen

## Endpoints

### 1. `/extract-calendar/`
Extrahiert Kalenderdaten aus PST/OST-Dateien.

**Method:** POST  
**Content-Type:** multipart/form-data

**Parameter:**
- `file`: PST/OST-Datei (erforderlich)
- `format`: Format der Extraktion ('csv' oder 'native', Standard: 'csv')
- `target_folder`: Optionaler Zielordner
- `return_file`: Ob die ZIP-Datei als Download zurückgegeben werden soll (Standard: false)
- `pst_folder`: Name des Ordners in der PST-Datei (Standard: "Calendar")
- `extract_all`: Ob alle Elemente extrahiert werden sollen (Standard: false)

### 2. `/extract-calendar-from-file`
Extrahiert Kalenderdaten aus hochgeladenen Dateien (ZIP, PST, OST).

**Method:** POST  
**Content-Type:** multipart/form-data

**Parameter:**
- `file`: Datei (ZIP, PST oder OST, erforderlich)
- `format`: Format der Extraktion ('csv' oder 'native', Standard: 'csv')
- `extract_all`: Ob alle Elemente extrahiert werden sollen (Standard: false)
- `return_file`: Ob die ZIP-Datei als Download zurückgegeben werden soll (Standard: false)
- `import_to_db`: Ob die Daten in die Datenbank importiert werden sollen (Standard: false)

### 3. `/import-csv-to-db` ⭐ **NEU**
Importiert Daten direkt aus einer CSV-Datei in die Datenbank.

**Method:** POST  
**Content-Type:** multipart/form-data

**Parameter:**
- `file`: CSV-Datei (erforderlich)
- `table_name`: Name der Zieltabelle (Standard: "calendar_data")
- `truncate_table`: Ob vorhandene Daten gelöscht werden sollen (Standard: true)

**Response:**
```json
{
  "status": "success",
  "message": "CSV-Datei erfolgreich in die Datenbank importiert",
  "filename": "calendar.csv",
  "table_name": "calendar_data",
  "imported_rows": 150,
  "truncated_table": true
}
```

### 4. `/list-pst-folders`
Listet alle Ordner in einer PST/OST-Datei auf.

**Method:** POST  
**Content-Type:** application/json

**Body:**
```json
{
  "filename": "example.pst"
}
```

### 5. `/health`
Überprüft die Anwendungsverfügbarkeit.

**Method:** GET

### 6. `/debug/files`
Zeigt den Inhalt des Anwendungsverzeichnisses an.

**Method:** GET

### 7. `/data/files`
Zeigt den Inhalt des Datenverzeichnisses an.

**Method:** GET

### 8. `/debug/dotnet`
Testet die .NET-Laufzeit und gibt Debug-Informationen zurück.

**Method:** GET

## Verwendung

### CSV-Datei direkt in Datenbank importieren

```bash
curl -X POST "http://localhost:8000/import-csv-to-db" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@calendar.csv" \
  -F "table_name=calendar_data" \
  -F "truncate_table=true"
```

### PST-Datei extrahieren und in Datenbank importieren

```bash
curl -X POST "http://localhost:8000/extract-calendar-from-file" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@calendar.pst" \
  -F "format=csv" \
  -F "import_to_db=true"
```

## Datenbank-Schema

Der Service verwendet ein Mapping-System, das in `app/config/calendar_mapping.json` definiert ist. Die Tabelle wird automatisch erstellt, basierend auf diesem Mapping.

## Docker

```bash
# Service starten
docker-compose up -d

# Logs anzeigen
docker-compose logs -f

# Service stoppen
docker-compose down
```

## Entwicklung

```bash
# Abhängigkeiten installieren
pip install -r requirements.txt

# Service starten
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Konfiguration

Die Datenbank-Konfiguration erfolgt über Umgebungsvariablen oder die `app/config/database.py` Datei.

Das Kalender-Mapping wird in `app/config/calendar_mapping.json` definiert und bestimmt, wie CSV-Spalten auf Datenbankfelder gemappt werden. 