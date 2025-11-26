# Implementierungskonzept: Meeting-Dropdown für NULL-Werte & manuellen Eintrag
## 1. Zielsetzung
Erweiterung der bestehenden Dropdown-Logik in der Transkriptions-Steuerungs-UI, sodass:
- das Dropdown auch erscheint, wenn `meeting_title` in `transcriptions` **NULL** ist (nicht nur bei `"Mehrere Meetings gefunden"`), und
- Nutzer:innen über einen festen Eintrag `manueller Eintrag…` am Ende der Dropdown-Liste einen frei wählbaren Meeting-Titel erfassen können, der zurück in die Tabelle `transcriptions` geschrieben wird.
## 2. Status-quo Analyse
### Frontend (`react-frontend/src/components/TranscriptionTable.tsx`)
- Dropdown wird nur gerendert, wenn `meeting_title === "Mehrere Meetings gefunden"`.
- Kalendereinträge werden pro Datum im Array `transcriptionsWithMultipleMeetings` geladen (`uniqueDates`, max. 10 Queries via `calendarApi.getByDay`).
- Rendering nutzt `<Select>` mit `meetingsByDate` Map, Value = Index des Meetings; Auswahl triggert `transcriptionApi.linkCalendar`.
- Kein Pfad für `meeting_title = NULL` oder manuellen Text.
### Backend (`react-frontend/server/server.js`)
- Endpoint `POST /api/transcriptions/:id/link-calendar` schreibt `meeting_title`, `meeting_start_date`, `participants`.
- Kein Endpoint, der ausschließlich einen frei eingegebenen Titel entgegennimmt.
### API-Layer (`react-frontend/src/lib/api.ts`)
- `transcriptionApi` kennt `getAll`, `deleteMultiple`, `updateLanguage`, `linkCalendar`.
- Kein dedizierter Call zum Setzen eines manuellen Meeting-Titels.
## 3. Soll-Konzept
### 3.1 UI/UX-Verhalten
1. **Dropdown-Anzeige**: Sobald `meeting_title` leer (`null`, `undefined`, `''`) **oder** `"Mehrere Meetings gefunden"` ist **und** `recording_date` existiert, wird das Dropdown angezeigt.
2. **Optionen**:
   - `Bitte wählen…`
   - Alle Kalendereinträge des Aufnahmetages (wie bisher).
   - Fester letzter Eintrag: `manueller Eintrag…`.
3. **Manueller Eintrag**:
   - Nach Auswahl wechselt die Zelle in einen Inline-Edit-Modus (Select + Input + Buttons) oder öffnet ein kleines Overlay direkt in der Zelle.
   - Input nutzt vorhandene UI-Komponenten (`Input`, `Button`).
   - Validierung: Pflichtfeld, max. 255 Zeichen (Deckelung wie `VARCHAR(255)`).
   - Speicherung via neuem API-Endpoint, danach Table-Refresh (`invalidateQueries(['transcriptions'])`).
### 3.2 Datenfluss
```
TranscriptionTable (Meeting-Zelle)
 ├─ prüft meeting_title (null/Mehrere)
 ├─ lädt meetingsByDate wie gehabt (erweitert auf NULL-Zustände)
 ├─ Dropdown-Wahl:
 │   ├─ regulärer Kalendereintrag → bestehendes linkCalendar
 │   └─ manueller Eintrag… → lokaler State → neuer Endpoint patchMeetingTitle
 └─ Erfolgreiche Mutation → React Query Invalidate → UI aktualisiert
```
### 3.3 Backend-Erweiterung
- **Neuer Endpoint**: `PATCH /api/transcriptions/:id/meeting-title`
  - Body: `{ meeting_title: string }`
  - SQL: `UPDATE transcriptions SET meeting_title = $1 WHERE id = $2 RETURNING *`
  - Optional: `updated_at` setzen (falls Spalte vorhanden).
  - Response analog zu anderen PATCH-Routen (`{ data: row, message: '...' }`).
  - Validierungen: Länge, nicht leer, ggf. Trim.
  - Logging & Fehlerbehandlung wie bestehende Endpoints.
- Keine Änderungen am Processing-Service nötig; Workflow setzt weiterhin `"Mehrere Meetings gefunden"` oder `NULL`.
## 4. Umsetzungsschritte (Cursor-ready)
### 4.1 Backend (`react-frontend/server/server.js`)
1. Am Kopf: ggf. Utility für Input-Validierung hinzufügen.
2. Unterhalb des Language-PATCH eine neue Route einfügen:
   ```js
   app.patch('/api/transcriptions/:id/meeting-title', async (req, res) => { ... });
   ```
3. Validieren (`meeting_title` vorhanden, String, max. 255).
4. Query ausführen, Fehlerfälle (404, 500) analog.
### 4.2 API-Layer (`react-frontend/src/lib/api.ts`)
1. Neue Funktion `updateMeetingTitle(id: number, title: string)`.
2. Exportieren und später in UI nutzen.
### 4.3 Frontend-Komponenten
#### Datenaufbereitung
- `transcriptionsWithMultipleMeetings`: Filter anpassen auf `(t.meeting_title === "Mehrere Meetings gefunden" || !t.meeting_title) && t.recording_date`.
- Map `meetingsByDate`: unverändert, aber Query-Limit prüfen (optional Parameterisieren, falls >10 Datumswerte vorkommen).
#### UI-Logik
1. **Hilfsfunktionen/State**:
   - `const [manualEdit, setManualEdit] = useState<{ id: number; value: string } | null>(null);`
   - Handler `handleManualSelect(transcription)` setzt `manualEdit`.
   - Handler `submitManualTitle` ruft `transcriptionApi.updateMeetingTitle`.
2. **Rendering** (`meeting_title` Spalte):
   ```tsx
   const needsDropdown = !meetingTitle || meetingTitle === 'Mehrere Meetings gefunden';
   if (!needsDropdown || !transcription.recording_date) return <span>{meetingTitle || '-'}</span>;
   ```
3. **Dropdown-Inhalt**:
   - Bestehende Meeting-Optionen + `<option value="manual">manueller Eintrag…</option>`.
4. **onChange**:
   - `if (value === 'manual') { setManualEdit({ id: transcription.id, value: meetingTitle ?? '' }); return; }`
   - Sonst wie bisher `linkCalendarMutation`.
5. **Render Manual Input**:
   - Direkt unterhalb des Selects oder als Ersatz, wenn `manualEdit?.id === transcription.id`.
   - Enthält `Input`, `Speichern`-Button (disabled bei leerem Wert), `Abbrechen`.
6. **Mutation**:
   - Neuer `useMutation` Hook `updateMeetingTitleMutation`.
   - Erfolgs-Callback: `invalidateQueries(['transcriptions'])`, `setManualEdit(null)`.
7. **Loading/Error Handling**:
   - Buttons disabled bei `isPending`.
   - Fehlermeldung (Toast oder inline) optional.
### 4.4 Tests & Validierung
- **Happy Paths**:
  - Transkription mit `"Mehrere Meetings gefunden"` → Dropdown + funktionierender Kalender-Link.
  - Transkription mit `NULL` → Dropdown + Kalender-Link.
  - Manueller Eintrag setzt Titel korrekt.
- **Edge Cases**:
  - `recording_date` fehlt → fallback Text, kein Dropdown.
  - Keine Meetings für den Tag → Dropdown enthält nur `Bitte wählen…` + `manueller Eintrag…`.
  - Eingabe leer → Speichern deaktiviert.
  - API-Fehler → Benutzerfeedback, State resetten.
- **Regression**: sicherstellen, dass bestehende Spaltenbreite-/Selection-Logik unverändert bleibt.
## 5. Offene Punkte / Klarstellungen
1. **Dropdown-Limit**: Ist `slice(0,10)` weiterhin ausreichend oder muss dynamisch erweitert werden?
2. **Meeting-Startdatum bei manuellem Eintrag**: Soll `meeting_start_date` geleert bleiben oder auf `recording_date` gesetzt werden?
3. **Teilnehmer-Feld**: Bleibt bei manuellem Eintrag unverändert (`participants` bleibt `NULL`)?
4. **UX**: Soll nach erfolgreicher manueller Speicherung der neue Titel als Text erscheinen (Dropdown verschwindet) oder weiter editierbar sein?

Dieses Dokument dient als ausführbarer Fahrplan für die Implementierung und berücksichtigt den bestehenden Code-Stand, ohne direkte Codeänderungen vorzunehmen.