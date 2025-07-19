# Processing Service

Der Processing Service ist verantwortlich für die Verarbeitung und Zuordnung von Transkriptionen zu Kalender-Meetings.

## Konfiguration

### Umgebungsvariablen

Die folgenden Umgebungsvariablen können in der `.env` Datei konfiguriert werden:

#### `MEETING_TIME_WINDOW_MINUTES`
- **Standardwert**: `5`
- **Beschreibung**: Definiert das Zeitfenster in Minuten, innerhalb dessen eine Transkription einem Meeting zugeordnet werden kann.
- **Beispiel**: 
  - `MEETING_TIME_WINDOW_MINUTES=5` - Transkriptionen werden Meetings zugeordnet, wenn sie maximal 5 Minuten vor oder nach dem Meeting-Zeitpunkt liegen
  - `MEETING_TIME_WINDOW_MINUTES=10` - Erweitert das Zeitfenster auf 10 Minuten für flexiblere Zuordnung

#### `TIMEZONE`
- **Standardwert**: `Europe/Berlin`
- **Beschreibung**: Zeitzone für die Verarbeitung von Datum/Uhrzeit-Werten
- **Mögliche Werte**: `UTC`, `Europe/Berlin`, `America/New_York`, etc.

## Endpoints

### `POST /get_meeting_info`
Sucht Meeting-Informationen basierend auf dem Aufnahmezeitpunkt einer Transkription oder verarbeitet automatisch alle Transkriptionen mit Status 'pending'.

**Request Body (optional):**
```json
{
  "recording_date": "2024-01-15 14-30"
}
```

**Verhalten:**
- **Mit recording_date**: Verarbeitet nur die angegebene Transkription
- **Ohne recording_date**: Verarbeitet automatisch alle Transkriptionen mit `transcription_status = 'pending'`

**Response (einzelne Transkription):**
```json
{
  "status": "success",
  "meeting_info": {
    "meeting_start_date": "2024-01-15T13:30:00Z",
    "meeting_end_date": "2024-01-15T14:30:00Z",
    "meeting_title": "Team Meeting",
    "meeting_location": "Conference Room A",
    "invitation_text": "Meeting invitation details",
    "participants": "Max;Anna;Tom"
  }
}
```

**Response (Batch-Verarbeitung):**
```json
{
  "status": "success",
  "processed": 3,
  "details": [
    {
      "id": 1,
      "meeting_info": {
        "meeting_start_date": "2024-01-15T13:30:00Z",
        "meeting_end_date": "2024-01-15T14:30:00Z",
        "meeting_title": "Team Meeting",
        "participants": "Max;Anna;Tom"
      }
    },
    {
      "id": 2,
      "error": "Kein Meeting im Zeitfenster von +/- 5 Minuten gefunden"
    },
    {
      "id": 3,
      "meeting_info": {
        "meeting_start_date": "2024-01-15T15:00:00Z",
        "meeting_end_date": "2024-01-15T16:00:00Z",
        "meeting_title": "Project Review",
        "participants": "Lisa;John"
      }
    }
  ]
}
```

**Funktionsweise:**
- Sucht nach Meetings im konfigurierten Zeitfenster (±`MEETING_TIME_WINDOW_MINUTES` Minuten)
- Wählt das Meeting aus, das zeitlich am nächsten am angegebenen Zeitpunkt liegt
- Bei Batch-Verarbeitung werden alle pending Transkriptionen abgearbeitet
- Erfolgreiche Zuordnungen werden in der Datenbank gespeichert
- Fehler werden in der Response dokumentiert, ohne die Verarbeitung zu stoppen

## Experimentieren mit verschiedenen Zeitfenstern

Um verschiedene Zeitfenster zu testen, ohne den Code zu ändern:

1. Ändern Sie den Wert in der `.env` Datei:
   ```bash
   # Für 10 Minuten Zeitfenster
   MEETING_TIME_WINDOW_MINUTES=10
   
   # Für 3 Minuten Zeitfenster (strenger)
   MEETING_TIME_WINDOW_MINUTES=3
   ```

2. Starten Sie den Service neu, damit die Änderungen wirksam werden.

3. Testen Sie mit verschiedenen Aufnahmezeitpunkten, um das optimale Zeitfenster für Ihre Anforderungen zu finden. 