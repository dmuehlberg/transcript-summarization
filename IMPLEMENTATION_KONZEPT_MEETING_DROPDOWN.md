# Implementierungskonzept: Meeting-Dropdown statt Aktionen-Spalte

## Übersicht

Dieses Konzept beschreibt die Umstellung der Meeting-Zuordnung im React Frontend von einem zweistufigen Prozess (Aktionen-Button → separater Calendar-Screen) zu einem direkten Dropdown-Feld in der `meeting_title` Spalte.

## Aktueller Zustand

### Frontend (React)
- **TranscriptionTable.tsx**: Enthält eine "Aktionen"-Spalte mit Button "Meeting wählen"
- **CalendarTable.tsx**: Separater Screen zur Auswahl eines Meetings aus einer Tabelle
- **App.tsx**: Verwaltet den Screen-Wechsel zwischen Dashboard und Calendar-Screen
- Das `meeting_title` Feld zeigt aktuell nur Text an

### Backend (Processing Service)
- **main.py** `/get_meeting_info` Endpoint:
  - Erkennt bereits, wenn mehrere Meetings gefunden werden (`len(rows) > 1`)
  - Setzt in diesem Fall `meeting_title = "Multiple Meetings found"` (englisch)
  - Aktualisiert die Transkription mit diesen Informationen

### Backend (React Server)
- **server.js** `/api/calendar` Endpoint:
  - Lädt Kalendereinträge für ein bestimmtes Datum aus `calendar_entries` Tabelle
  - Wird aktuell vom CalendarTable verwendet

## Anforderungen

1. **Text-Änderung**: "Multiple Meetings found" → "mehrere Meetings gefunden" (deutsch)
2. **Entfernen der Aktionen-Spalte**: Die gesamte "Aktionen"-Spalte soll entfernt werden
3. **Entfernen des Calendar-Screens**: CalendarTable.tsx und zugehörige Navigation entfernen
4. **Dropdown im meeting_title Feld**: 
   - Wenn `meeting_title = "mehrere Meetings gefunden"` → Dropdown anzeigen
   - Dropdown zeigt alle Meetings des gleichen Tages (Startzeit + Meeting-Titel)
   - Auswahl aktualisiert die Transkription mit den Meeting-Informationen
5. **Backend-Anpassungen**: 
   - Prüfung ob `/get_meeting_info` Endpoint angepasst werden muss
   - Neuer Endpoint oder Erweiterung für das Laden aller Meetings eines Tages

## Implementierungsschritte

### Phase 1: Backend-Anpassungen

#### 1.1 Processing Service - Text-Änderung
**Datei**: `processing_service/app/main.py`

**Änderungen**:
- Zeile 224: `"meeting_title": "Multiple Meetings found"` → `"meeting_title": "mehrere Meetings gefunden"`
- Zeile 298: `"meeting_title": "Multiple Meetings found"` → `"meeting_title": "mehrere Meetings gefunden"`

**Begründung**: Konsistente deutsche Lokalisierung

#### 1.2 Processing Service - Neuer Endpoint für Tages-Meetings
**Datei**: `processing_service/app/main.py`

**Neuer Endpoint**: `GET /get_meetings_by_date`

**Funktionalität**:
- Parameter: `recording_date` (Format: `YYYY-MM-DD` oder `YYYY-MM-DD HH-MM`)
- Extrahiert das Datum (ohne Uhrzeit) aus `recording_date`
- Sucht alle Meetings aus `calendar_data` Tabelle für diesen Tag
- Gibt Liste zurück mit: `id`, `start_date`, `end_date`, `subject`, `location`, `display_to`, `display_cc`

**SQL Query**:
```sql
SELECT start_date, end_date, subject, has_picture, user_entry_id, display_to, display_cc
FROM calendar_data
WHERE DATE(start_date AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin') = DATE(:recording_date AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')
ORDER BY start_date ASC
```

**Response Format**:
```json
{
  "status": "success",
  "meetings": [
    {
      "start_date": "2024-01-15T13:30:00Z",
      "end_date": "2024-01-15T14:30:00Z",
      "subject": "Team Meeting",
      "location": "...",
      "participants": "Max;Anna;Tom"
    }
  ]
}
```

**Alternative**: Erweiterung des bestehenden `/get_meeting_info` Endpoints mit optionalem Parameter `get_all_day_meetings=true`

#### 1.3 React Server - Neuer Endpoint für Tages-Meetings
**Datei**: `react-frontend/server/server.js`

**Neuer Endpoint**: `GET /api/calendar/day`

**Funktionalität**:
- Parameter: `date` (Format: `YYYY-MM-DD`)
- Lädt alle Meetings aus `calendar_entries` Tabelle für diesen Tag
- Gibt formatierte Liste zurück

**SQL Query**:
```sql
SELECT id, subject, start_date, end_date, location, attendees
FROM calendar_entries
WHERE DATE(start_date) = DATE($1)
ORDER BY start_date ASC
```

**Alternative**: Erweiterung des bestehenden `/api/calendar` Endpoints

**Hinweis**: Es muss geklärt werden, ob `calendar_entries` oder `calendar_data` verwendet werden soll. Aktuell verwendet:
- Processing Service: `calendar_data`
- React Server: `calendar_entries`

**Empfehlung**: Konsistente Verwendung einer Tabelle oder Synchronisation zwischen beiden Tabellen.

### Phase 2: Frontend-Anpassungen

#### 2.1 API-Erweiterung
**Datei**: `react-frontend/src/lib/api.ts`

**Neue Funktion**:
```typescript
// In calendarApi Objekt
getByDay: async (date: string): Promise<ApiResponse<CalendarEntry[]>> => {
  const response = await api.get('/calendar/day', { params: { date } });
  return response.data;
},
```

**Alternative**: Erweiterung von `getByDate` um beide Verwendungszwecke zu unterstützen

#### 2.2 TranscriptionTable - Aktionen-Spalte entfernen
**Datei**: `react-frontend/src/components/TranscriptionTable.tsx`

**Änderungen**:
- Zeilen 279-304: Entfernen der gesamten "Aktionen"-Spalte Definition
- Zeile 25: `onSelectMeeting` Prop entfernen (wird nicht mehr benötigt)

#### 2.3 TranscriptionTable - meeting_title als Dropdown
**Datei**: `react-frontend/src/components/TranscriptionTable.tsx`

**Neue Funktionalität**:
- Import von `useQuery` für das Laden der Meetings eines Tages
- State für ausgewählte Meeting-ID pro Zeile
- Mutation für das Aktualisieren der Transkription mit Meeting-Daten

**Logik**:
1. Prüfen ob `meeting_title === "mehrere Meetings gefunden"`
2. Wenn ja:
   - `recording_date` aus der Transkription extrahieren
   - Datum extrahieren (nur Tag, ohne Uhrzeit)
   - Query für Meetings des Tages ausführen
   - Dropdown anzeigen mit Format: `"HH:MM - Meeting-Titel"`
   - Bei Auswahl: Mutation zum Aktualisieren der Transkription
3. Wenn nein:
   - Normale Text-Anzeige wie bisher

**Dropdown-Format**:
- Optionen: `"HH:MM - {subject}"` (z.B. "13:30 - Team Meeting")
- Value: Index oder ID des Meetings
- Bei Auswahl: Vollständige Meeting-Informationen an Backend senden

**Mutation**:
- Verwendet bestehenden `transcriptionApi.linkCalendar` Endpoint
- Sendet: `subject`, `start_date`, `end_date`, `location`, `attendees`

**Code-Struktur**:
```typescript
// In der meeting_title Spalten-Definition
cell: ({ row, getValue }) => {
  const meetingTitle = getValue();
  const transcription = row.original;
  
  // Prüfe ob mehrere Meetings gefunden
  if (meetingTitle === "mehrere Meetings gefunden") {
    // Extrahiere Datum aus recording_date
    const recordingDate = transcription.recording_date;
    const dateOnly = recordingDate ? new Date(recordingDate).toISOString().split('T')[0] : null;
    
    // Lade Meetings des Tages
    const { data: meetingsData } = useQuery({
      queryKey: ['calendar-day', dateOnly],
      queryFn: () => calendarApi.getByDay(dateOnly),
      enabled: !!dateOnly,
    });
    
    // Dropdown mit Meetings
    return (
      <Select
        value={selectedMeetingId || ''}
        onChange={(e) => handleMeetingSelect(transcription.id, e.target.value, meetingsData)}
      >
        <option value="">Bitte wählen...</option>
        {meetingsData?.data.map((meeting, index) => (
          <option key={index} value={index}>
            {formatTime(meeting.start_date)} - {meeting.subject}
          </option>
        ))}
      </Select>
    );
  }
  
  // Normale Anzeige
  return <span>{meetingTitle}</span>;
}
```

**Hinweis**: `useQuery` kann nicht direkt in einer Cell-Funktion verwendet werden. Stattdessen:
- Query auf Zeilen-Ebene durchführen (für alle Zeilen mit "mehrere Meetings gefunden")
- Oder Custom Hook erstellen
- Oder Query außerhalb der Tabelle und per Props übergeben

**Besserer Ansatz**: 
- Alle Transkriptionen mit "mehrere Meetings gefunden" identifizieren
- Für jedes eindeutige Datum eine Query durchführen
- Ergebnisse in einem State/Map speichern
- In der Cell-Funktion darauf zugreifen

#### 2.4 App.tsx - Calendar-Screen entfernen
**Datei**: `react-frontend/src/App.tsx`

**Änderungen**:
- Zeile 4: Import von `CalendarTable` entfernen
- Zeilen 8-11: `CalendarScreenState` Interface entfernen
- Zeile 15: `calendarState` State entfernen
- Zeilen 17-20: `handleSelectMeeting` Funktion entfernen
- Zeilen 22-30: `handleCalendarBack` und `handleCalendarSuccess` Funktionen entfernen
- Zeilen 52-59: Calendar-Screen Rendering entfernen
- Zeile 48: `onSelectMeeting` Prop aus TranscriptionTable entfernen

#### 2.5 CalendarTable.tsx - Datei entfernen
**Datei**: `react-frontend/src/components/CalendarTable.tsx`

**Aktion**: Datei komplett löschen (wird nicht mehr benötigt)

### Phase 3: Datenformatierung

#### 3.1 Zeitformatierung für Dropdown
**Datei**: `react-frontend/src/lib/data-formatters.ts`

**Neue Funktion**:
```typescript
export const formatTime = (dateString: string | null): string => {
  if (!dateString) return '-';
  try {
    const date = new Date(dateString);
    return date.toLocaleTimeString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateString;
  }
};
```

### Phase 4: Testing & Validierung

#### 4.1 Test-Szenarien
1. **Einzelnes Meeting gefunden**: Normale Anzeige wie bisher
2. **Mehrere Meetings gefunden**: Dropdown erscheint mit allen Meetings des Tages
3. **Kein Meeting gefunden**: Normale Anzeige (kein Dropdown)
4. **Meeting-Auswahl**: Transkription wird korrekt aktualisiert
5. **Mehrere Transkriptionen mit mehreren Meetings**: Jede Zeile zeigt eigenes Dropdown

#### 4.2 Edge Cases
- `recording_date` ist null → Kein Dropdown anzeigen
- Keine Meetings für den Tag gefunden → Fehlermeldung oder leeres Dropdown
- Meeting-Auswahl schlägt fehl → Fehlerbehandlung und Rollback

## Offene Fragen / Klärungsbedarf

1. **Tabellen-Konsistenz**: 
   - Soll `calendar_entries` oder `calendar_data` verwendet werden?
   - Müssen beide Tabellen synchronisiert werden?

2. **Datum-Extraktion**:
   - Wie wird das Datum aus `recording_date` extrahiert?
   - Welche Zeitzone soll verwendet werden?

3. **Meeting-Format im Dropdown**:
   - Soll nur Startzeit + Titel angezeigt werden?
   - Sollen weitere Informationen (Ort, Teilnehmer) angezeigt werden?

4. **Performance**:
   - Wie viele Transkriptionen können gleichzeitig "mehrere Meetings gefunden" haben?
   - Sollen Queries gebündelt werden (ein Query für alle eindeutigen Daten)?

5. **Backend-Endpoint**:
   - Soll ein neuer Endpoint erstellt werden oder der bestehende erweitert werden?
   - Soll der Processing Service oder React Server die Meetings liefern?

## Empfohlene Reihenfolge

1. **Backend-Text-Änderung** (Phase 1.1) - Einfach, keine Abhängigkeiten
2. **Backend-Endpoint** (Phase 1.2 oder 1.3) - Muss vor Frontend-Änderungen fertig sein
3. **Frontend API-Erweiterung** (Phase 2.1) - Abhängig von Backend-Endpoint
4. **Frontend Dropdown-Implementierung** (Phase 2.3) - Kernfunktionalität
5. **Aktionen-Spalte entfernen** (Phase 2.2) - Kann parallel zu 2.3 erfolgen
6. **Calendar-Screen entfernen** (Phase 2.4, 2.5) - Cleanup nach Dropdown-Implementierung
7. **Formatierung** (Phase 3.1) - Unterstützend für Dropdown
8. **Testing** (Phase 4) - Abschluss

## Risiken & Mitigation

1. **Performance bei vielen Transkriptionen**:
   - **Risiko**: Viele Queries für Meetings pro Tag
   - **Mitigation**: Queries bündeln, Caching implementieren

2. **Zeitzonen-Probleme**:
   - **Risiko**: Falsche Meetings werden angezeigt
   - **Mitigation**: Konsistente Zeitzonen-Behandlung, Tests mit verschiedenen Zeitzonen

3. **Tabellen-Inkonsistenz**:
   - **Risiko**: Meetings werden nicht gefunden
   - **Mitigation**: Klärung welche Tabelle verwendet wird, ggf. Synchronisation

4. **User Experience**:
   - **Risiko**: Dropdown zu groß bei vielen Meetings
   - **Mitigation**: Limitierung der Anzeige, Suche im Dropdown

## Zusammenfassung

Die Implementierung umfasst:
- ✅ Text-Änderung im Processing Service (deutsch)
- ✅ Neuer/erweiterter Backend-Endpoint für Tages-Meetings
- ✅ Entfernen der Aktionen-Spalte
- ✅ Entfernen des Calendar-Screens
- ✅ Dropdown im meeting_title Feld
- ✅ Mutation für Meeting-Auswahl
- ✅ Formatierung und Hilfsfunktionen

**Geschätzter Aufwand**: 4-6 Stunden
**Komplexität**: Mittel
**Breaking Changes**: Ja (API-Änderungen, Frontend-Struktur)

