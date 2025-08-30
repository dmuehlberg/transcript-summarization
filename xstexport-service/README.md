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
- `source`: Quelle der CSV-Datei ("internal" oder "external", Standard: "internal")

**Unterstützte Quellen:**
- `internal`: Für intern erzeugte CSV-Dateien (Standard-Format)
- `external`: Für extern erzeugte CSV-Dateien (mit anderen Spaltennamen)

**Beispiel curl-Befehle:**
```bash
# Intern erzeugte CSV-Datei
curl -X POST "http://localhost:8000/import-calendar-csv" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@calendar_data.csv" \
  -F "table_name=calendar_data" \
  -F "source=internal"

# Extern erzeugte CSV-Datei
curl -X POST "http://localhost:8000/import-calendar-csv" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@external_calendar.csv" \
  -F "table_name=calendar_data" \
  -F "source=external"
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

## Unterstützte CSV-Felder

Der Service unterstützt folgende CSV-Felder für Kalenderdaten:

### Standard-Felder
- **Subject**: Betreff des Termins
- **Start Date**: Startdatum/-zeit des Termins
- **End Date**: Enddatum/-zeit des Termins
- **Conversation Topic**: Gesprächsthema
- **Sender Name**: Name des Absenders
- **Display Cc**: CC-Empfänger
- **Display To**: Hauptempfänger
- **Creation Time**: Erstellungszeitpunkt
- **Last Modification Time**: Letzte Änderungszeit

### Terminserien-Felder (NEU)
- **Address Book Extension Attribute1** → `meeting_series_rhythm`: Rhythmus der Terminserie (z.B. wöchentlich, monatlich)
- **Contact Item Data** → `meeting_series_start_date`: Startdatum der Terminserie
- **Address Book Is Member Of Distribution List** → `meeting_series_end_date`: Enddatum der Terminserie

### Externe CSV-Felder
Für extern erzeugte CSV-Dateien werden alternative Feldnamen unterstützt:
- **AddressBookExtensionAttribute1** → `meeting_series_rhythm`
- **ContactItemData** → `meeting_series_start_date`
- **AddressBookIsMemberOfDistributionList** → `meeting_series_end_date`

Alle Datumsfelder werden automatisch in UTC konvertiert und gespeichert.

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

Tests für den CSV-Import-Endpoint sind verfügbar:

### Externes CSV-Format testen
```bash
python test_external_csv_import.py
```

### Internes CSV-Format mit neuen Terminserien-Feldern testen
```bash
python test_internal_csv_import.py
```

Die Tests erstellen Test-CSV-Dateien mit den neuen Terminserien-Feldern und senden sie an den `/import-calendar-csv` Endpoint. Stellen Sie sicher, dass der Service läuft, bevor Sie die Tests ausführen.

**Getestete neue Felder:**
- `Address Book Extension Attribute1` → `meeting_series_rhythm`
- `Contact Item Data` → `meeting_series_start_date`  
- `Address Book Is Member Of Distribution List` → `meeting_series_end_date` 