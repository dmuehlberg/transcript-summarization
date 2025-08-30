# Implementierungskonzept: Erweiterung des CSV-Imports um zusätzliche Kalenderfelder

## Übersicht
Das Konzept beschreibt die Integration von drei zusätzlichen CSV-Feldern in den bestehenden `/import-calendar-csv` Endpoint des xstexport-service. Diese Felder werden in die `calendar_data` Tabelle eingefügt und repräsentieren Informationen über Terminserien.

## Zu integrierende Felder

| CSV-Feld | Datenbankfeld | Beschreibung |
|----------|---------------|--------------|
| `Address Book Extension Attribute1` | `meeting_series_rhythm` | Rhythmus der Terminserie (z.B. wöchentlich, monatlich) |
| `Contact Item Data` | `meeting_series_start_date` | Startdatum der Terminserie |
| `Address Book Is Member Of Distribution List` | `meeting_series_end_date` | Enddatum der Terminserie |

## Implementierungsschritte

### 1. Aktualisierung der Datenbankstruktur

#### 1.1 Erweiterung der Mapping-Konfiguration
Die Datei `app/config/calendar_mapping.json` muss um die neuen Felder erweitert werden:

```json
{
    "mappings": {
        // ... bestehende Felder ...
        "Address Book Extension Attribute1": {
            "pg_field": "meeting_series_rhythm",
            "pg_type": "text"
        },
        "Contact Item Data": {
            "pg_field": "meeting_series_start_date",
            "pg_type": "timestamp with time zone"
        },
        "Address Book Is Member Of Distribution List": {
            "pg_field": "meeting_series_end_date",
            "pg_type": "timestamp with time zone"
        }
    },
    "external_mappings": {
        // ... bestehende Felder ...
        "Address Book Extension Attribute1": {
            "pg_field": "meeting_series_rhythm",
            "pg_type": "text"
        },
        "Contact Item Data": {
            "pg_field": "meeting_series_start_date",
            "pg_type": "timestamp with time zone"
        },
        "Address Book Is Member Of Distribution List": {
            "pg_field": "meeting_series_end_date",
            "pg_type": "timestamp with time zone"
        }
    }
}
```

#### 1.2 Datenbank-Migration
Die bestehende Tabelle `calendar_data` muss um die neuen Spalten erweitert werden. Dies geschieht automatisch durch den bestehenden `create_table_if_not_exists` Mechanismus.

### 2. Anpassung des DatabaseService

#### 2.1 Erweiterung der Datentyp-Konvertierung
In der `import_csv_to_db` Methode der `DatabaseService` Klasse müssen die neuen Felder bei der Datentyp-Konvertierung berücksichtigt werden:

- `meeting_series_rhythm`: Textfeld (keine spezielle Behandlung erforderlich)
- `meeting_series_start_date`: Timestamp mit Zeitzone (UTC-Konvertierung wie bei anderen Datumsfeldern)
- `meeting_series_end_date`: Timestamp mit Zeitzone (UTC-Konvertierung wie bei anderen Datumsfeldern)

#### 2.2 Datenbereinigung
Die neuen Textfelder müssen in die bestehende Bereinigungslogik für Textfelder integriert werden (Whitespace-Entfernung, Control-Character-Bereinigung).

### 3. Integration in den Startup-Prozess

#### 3.1 Automatische Tabellenerstellung
Die neuen Felder werden automatisch beim Service-Start durch die bestehende `startup_event` Funktion integriert, da diese `create_table_if_not_exists()` aufruft.

## Technische Details

### Datentypen
- **meeting_series_rhythm**: `TEXT` - Speichert den Rhythmus als String
- **meeting_series_start_date**: `TIMESTAMP WITH TIME ZONE` - UTC-formatierte Startzeit
- **meeting_series_end_date**: `TIMESTAMP WITH TIME ZONE` - UTC-formatierte Endzeit

### Zeitzonenbehandlung
Alle neuen Datumsfelder werden automatisch in UTC konvertiert, konsistent mit der bestehenden Implementierung.

### Rückwärtskompatibilität
Die Erweiterung ist vollständig rückwärtskompatibel:
- Bestehende CSV-Dateien ohne die neuen Felder funktionieren weiterhin
- Die neuen Felder werden bei fehlenden Werten als `NULL` gespeichert
- Keine Änderungen an bestehenden API-Endpunkten erforderlich

## Implementierungsreihenfolge

1. **Mapping-Konfiguration erweitern** - Neue Felder in `calendar_mapping.json` hinzufügen
2. **Datenbankstruktur aktualisieren** - Service neu  bauen und starten für automatische Tabellenerweiterung
3. **Dokumentation aktualisieren** - README.md und API-Dokumentation erweitern

Diese Implementierung nutzt die bestehende Architektur des Services und erweitert sie um die gewünschten Felder, ohne die bestehende Funktionalität zu beeinträchtigen.
