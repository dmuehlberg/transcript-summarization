# Implementierungskonzept: AWS Host-Einstellungen im React Frontend
## Übersicht
Dieses Dokument beschreibt die Implementierung eines Text-Eingabefeldes im React Frontend für die AWS-Instanz IP-Adresse/Hostname, die in der n8n-Datenbank gespeichert werden soll.
## Anforderungen
1. **Frontend**: Text-Eingabefeld im Bereich "Workflow-Steuerung" für AWS Host/IP
2. **Datenbank**: Neue Tabelle `transcription_settings` mit Spalten `parameter` und `value` in Datenbank n8n
3. **Processing Service**: Automatische Tabellenerstellung beim Start
4. **Backend API**: Endpunkte zum Lesen und Schreiben der Settings
5. **Frontend Integration**: Laden und Speichern des AWS Host-Wertes beim Laden/Refresh
## Architektur-Übersicht
```
React Frontend (WorkflowControls.tsx)
    ↓ API Call
Express Backend (server.js)
    ↓ SQL Query
PostgreSQL (n8n Datenbank)
    ↑ Tabellenerstellung
Processing Service (db.py init_db())
```
## Implementierungsschritte
### 1. Datenbank-Schema (Processing Service)
**Datei**: `processing_service/app/db.py`
**Änderung in `init_db()` Funktion**:
- Prüfung, ob Tabelle `transcription_settings` existiert
- Falls nicht vorhanden: Erstellung der Tabelle mit:
  - `parameter` (TEXT, PRIMARY KEY)
  - `value` (TEXT)
**SQL-Schema**:
```sql
CREATE TABLE IF NOT EXISTS transcription_settings (
    parameter TEXT PRIMARY KEY,
    value TEXT
);
```
**Neue Funktion `get_transcription_setting(parameter: str) -> str | None`**:
- Liest einen Setting-Wert aus der Datenbank
- Parameter: `parameter` (z.B. "aws_host")
- Rückgabe: `value` oder `None` wenn nicht vorhanden
**Neue Funktion `upsert_transcription_setting(parameter: str, value: str)`**:
- Speichert oder aktualisiert einen Setting-Wert
- Verwendet `INSERT ... ON CONFLICT DO UPDATE` für Upsert-Operation
### 2. Backend API-Endpunkte (Express Server)
**Datei**: `react-frontend/server/server.js`
**Neuer Endpoint: `GET /api/transcription-settings/:parameter`**:
- Liest einen spezifischen Setting-Wert aus der Datenbank
- Parameter: `parameter` (z.B. "aws_host")
- Response: `{ data: { parameter: string, value: string | null }, message: string }`
- Fehlerbehandlung: 404 wenn Parameter nicht existiert, 500 bei DB-Fehler
**Neuer Endpoint: `PUT /api/transcription-settings/:parameter`**:
- Speichert oder aktualisiert einen Setting-Wert
- Request Body: `{ value: string }`
- Response: `{ data: { parameter: string, value: string }, message: string }`
- Verwendet UPSERT-Logik (INSERT ... ON CONFLICT DO UPDATE)
**Neuer Endpoint: `GET /api/transcription-settings`** (optional, für alle Settings):
- Liest alle Settings aus der Datenbank
- Response: `{ data: Array<{ parameter: string, value: string }>, message: string }`
### 3. Frontend API-Client
**Datei**: `react-frontend/src/lib/api.ts`
**Neue API-Funktion `transcriptionSettingsApi`**:
```typescript
export const transcriptionSettingsApi = {
  get: async (parameter: string): Promise<ApiResponse<{ parameter: string; value: string | null }>> => {
    const response = await api.get(`/transcription-settings/${parameter}`);
    return response.data;
  },
  
  update: async (parameter: string, value: string): Promise<ApiResponse<{ parameter: string; value: string }>> => {
    const response = await api.put(`/transcription-settings/${parameter}`, { value });
    return response.data;
  },
};
```
### 4. TypeScript Types
**Datei**: `react-frontend/src/lib/types.ts`
**Neue Interfaces**:
```typescript
export interface TranscriptionSetting {
  parameter: string;
  value: string | null;
}
```
### 5. React Frontend Komponente
**Datei**: `react-frontend/src/components/WorkflowControls.tsx`
**Änderungen**:
1. **Import**: `transcriptionSettingsApi` aus `@/lib/api` importieren
2. **State Management**: 
   - `useState` für lokalen AWS Host-Wert
   - `useQuery` für Laden des Wertes beim Mount/Refresh
   - `useMutation` für Speichern des Wertes
3. **UI-Element**: 
   - Neues Text-Eingabefeld mit Label "AWS Host/IP"
   - Platzierung im Bereich "Workflow-Steuerung" (nach den Health-Status-Anzeigen oder vor den Buttons)
   - Optional: Speichern-Button oder Auto-Save bei Blur/Enter
4. **Query-Integration**:
   - Query Key: `['transcription-settings', 'aws_host']`
   - Query Function: `() => transcriptionSettingsApi.get('aws_host')`
   - Refetch beim Mount und bei Bedarf
5. **Mutation-Integration**:
   - Mutation Function: `(value: string) => transcriptionSettingsApi.update('aws_host', value)`
   - Success Callback: Query invalidieren für Refetch
   - Error Handling: Fehlermeldung anzeigen
**UI-Layout-Vorschlag**:
```tsx
<div className="mt-4">
  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
    AWS Host/IP
  </label>
  <input
    type="text"
    value={awsHostValue}
    onChange={(e) => setAwsHostValue(e.target.value)}
    onBlur={handleSaveAwsHost}
    placeholder="z.B. 192.168.1.100 oder ec2-xxx.amazonaws.com"
    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
  />
  {saveMutation.isPending && (
    <span className="text-xs text-gray-500 mt-1">Speichere...</span>
  )}
</div>
```
## Datenfluss
### Initiales Laden
1. React Frontend: `WorkflowControls` Komponente wird gemountet
2. `useQuery` triggert automatisch
3. API Call: `GET /api/transcription-settings/aws_host`
4. Express Backend: SQL Query `SELECT value FROM transcription_settings WHERE parameter = 'aws_host'`
5. PostgreSQL: Gibt Wert zurück (oder NULL wenn nicht vorhanden)
6. Frontend: Wert wird in State gesetzt und im Input-Feld angezeigt
### Speichern
1. Benutzer ändert Wert im Input-Feld
2. Benutzer verlässt Feld (onBlur) oder drückt Enter
3. `useMutation` wird getriggert
4. API Call: `PUT /api/transcription-settings/aws_host` mit `{ value: "..." }`
5. Express Backend: SQL Query `INSERT ... ON CONFLICT DO UPDATE`
6. PostgreSQL: Wert wird gespeichert/aktualisiert
7. Frontend: Query wird invalidiert, Wert wird neu geladen
## Fehlerbehandlung
### Datenbank-Fehler
- **Tabelle existiert nicht**: Wird automatisch beim nächsten Processing Service Start erstellt
- **Verbindungsfehler**: Fehlermeldung im Frontend, Retry-Logik optional
### API-Fehler
- **404 (Parameter nicht gefunden)**: Behandelt als "Wert nicht gesetzt", Input-Feld bleibt leer
- **500 (Server-Fehler)**: Fehlermeldung im Frontend, Benutzer kann erneut versuchen
### Frontend-Fehler
- **Validierung**: Optional IP/Hostname-Validierung vor dem Speichern
- **Network-Fehler**: Axios Interceptor zeigt Fehlermeldung
## Datenbank-Migration
### Bestehende Installationen
- Die Tabelle wird automatisch beim nächsten Start des Processing Service erstellt
- Keine manuelle Migration erforderlich
- Bestehende Daten bleiben unverändert
### Neue Installationen
- Tabelle wird automatisch beim ersten Start erstellt
- Keine zusätzlichen Schritte erforderlich
## Erweiterbarkeit
Die Implementierung ist so gestaltet, dass weitere Settings einfach hinzugefügt werden können:
1. **Neue Parameter**: Einfach neue Parameter-Werte in der Tabelle speichern
2. **Frontend-Erweiterung**: Weitere Input-Felder können nach dem gleichen Muster hinzugefügt werden
3. **API-Erweiterung**: Bestehende Endpoints unterstützen bereits beliebige Parameter
## Abhängigkeiten
- **Keine neuen Dependencies erforderlich**
- Alle benötigten Bibliotheken sind bereits vorhanden:
  - React Query (TanStack Query) für State Management
  - Axios für HTTP-Requests
  - PostgreSQL Driver (pg) im Backend
  - psycopg2 im Processing Service
## Implementierungsreihenfolge
1. ✅ **Schritt 1**: Datenbank-Schema in `processing_service/app/db.py` erweitern
2. ✅ **Schritt 2**: Backend API-Endpoints in `react-frontend/server/server.js` hinzufügen
3. ✅ **Schritt 3**: Frontend API-Client in `react-frontend/src/lib/api.ts` erweitern
4. ✅ **Schritt 4**: TypeScript Types in `react-frontend/src/lib/types.ts` hinzufügen
5. ✅ **Schritt 5**: React Komponente `WorkflowControls.tsx` erweitern
## Zusammenfassung
Diese Implementierung ermöglicht es Benutzern, die AWS-Instanz IP-Adresse/Hostname über das React Frontend zu konfigurieren. Die Daten werden persistent in der n8n-Datenbank gespeichert und automatisch beim Laden der Seite abgerufen. Die Lösung ist erweiterbar für weitere Settings und folgt den bestehenden Architektur-Patterns des Projekts.
