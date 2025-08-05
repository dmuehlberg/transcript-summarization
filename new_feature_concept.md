Implementierungskonzept Webapp „Transkriptions-Steuerung“ 

1. Architektur & Containerisierung
• Ziel: Docker-Container hostet eine React-Single-Page-App mit Express‑Backend.
• Backend
	- Node.js/Express, Verbindung zu PostgreSQL mit Connection Pool (pg.Pool, min=1, max=10).
	- RealDictCursor für objektbasierte Resultate.
• Frontend
	- React 18 + Vite, Shadcn/ui (Tailwind), TanStack Table v8, TanStack Query.
	- SPA läuft auf Port 8400.
• Docker
	- Multi‑Stage Dockerfile: Build + Runtime.
	- docker-compose.yml mit Service webapp, env_file: .env, Port-Mapping 8400:8400, gemeinsames Netzwerk mit Postgres.
2. API & Backend-Funktionen
+--------------------------------------------+--------+------------------------------------------------------------------------------------------+
| Endpoint                                   | Methode| Beschreibung                                                                             |
+--------------------------------------------+--------+------------------------------------------------------------------------------------------+
| /api/transcriptions                        | GET    | Liste aller Transkriptionen (inkl. Filter, Suche, Pagination).                          |
| /api/transcriptions                        | DELETE | Löscht mehrere Transkriptionen per ID-Liste.                                            |
| /api/transcriptions/:id/language           | PATCH  | Aktualisiert set_language (Inline-Edit).                                                |
| /api/transcriptions/:id/link-calendar      | POST   | Überträgt Kalenderdaten in eine Transkription.                                          |
| /api/calendar                              | GET    | Kalenderdaten, gefiltert nach start_date.                                               |
| /api/workflow/start                        | POST   | Triggert n8n-Workflow (GET http://n8n:5678/webhook/start-transcription).                |
| /api/workflow/status                       | GET    | Status des n8n-Workflows (active, running, etc.).                                       |
| /api/health                                | GET    | Verbindungstest zu Datenbank & n8n-Service.                                             |
+--------------------------------------------+--------+------------------------------------------------------------------------------------------+
• DB-Operationen (CRUD & Transaktionen)
	- get_transcriptions, update_transcription_language, delete_transcriptions, update_meeting_data, get_calendar_data_by_date.
	- Alle kritischen Updates in Transaktionen.
• Error Handling & Monitoring
	- Try‑Catch in allen Endpoints, Logging (z. B. winston).
	- Fehlerantworten mit aussagekräftigen Messages.
	- health-Endpoint checkt DB & n8n-Verfügbarkeit; Frontend zeigt Status-Badges.
3. Frontend-Struktur

react-frontend/
 ├─ src/
 │   ├─ components/
 │   │   ├─ TranscriptionTable.tsx
 │   │   ├─ CalendarTable.tsx
 │   │   ├─ WorkflowControls.tsx
 │   │   └─ StatusBadge.tsx
 │   ├─ lib/
 │   │   ├─ api.ts (Axios/TanStack Query Client, Retry/Timeout)
 │   │   ├─ data-formatters.ts (prepare_transcriptions_data, format_duration, get_status_color …)
 │   │   └─ types.ts
 │   ├─ App.tsx
 │   └─ main.tsx
 ├─ tailwind.config.js
 └─ index.html
4. Screen 1 – Transkriptions-Dashboard
• WorkflowControls
	- Button „Start Transcription“ → /api/workflow/start
	- Statusanzeige via useQuery (Polling refetchInterval).
	- n8n-Verfügbarkeit über /api/health.
• TranscriptionTable
	- TanStack Table mit Query-Integration (Live-Refetch).
	- Spalten: filename, transcription_status, set_language (Dropdown, Inline-Patch), meeting_title, meeting_start_date, participants, transcription_duration, audio_duration, created_at, detected_language, transcript_text, corrected_text, recording_date, id, Select Meeting, Checkbox-Spalte.
	- Interaktiv: Sortierung, Gruppierung, Filter (Status, Sprache), Textsuche, Resize, Pagination (20 Zeilen), Checkbox-Row-Selection.
• Aktionen:
	- Mehrfachlöschung markierter Transkriptionen.
	- Button „Select Meeting“ öffnet CalendarTable unterhalb.
5. Screen 2 – Calendar Entry Selection
• Wird mit transcription_id + start_date aufgerufen.
• Zeigt ausgewählte Transkriptionsinfos oben.
• TanStack Table mit Kalenderdaten (subject, start_date, Button „Select“).
• Beim Klick: POST /api/transcriptions/:id/link-calendar → Meeting‑Daten in transcriptions schreiben.
• Automatisches Zurückspringen zum Dashboard nach erfolgreichem Update.
• „Zurück“-Button zum Abbrechen.
6. Datenverarbeitung (Utilities)
• prepare_transcriptions_data
	- Sortieren, Filtern, Datumsformat (YYYY-MM-DD HH:MM), format_duration (Sek → MM:SS).
• prepare_calendar_data
	- Formatierung, Sortierung.
• get_status_color
	- Liefert CSS-Klassen für Badges (z. B. bg-green-500).
7. Benutzeroberfläche & UX
• Shadcn/ui-Komponenten: Buttons, Tabellen, Dropdowns, Dialoge, Badges.
• Modernes Design (Dark-/Light-Mode), responsive Layout.
• Status-Badges mit Farbcodierung.
• Fehlerhinweise per Toast/Alert.
• Nach Kalenderzuordnung Auto-Refresh des Dashboards.
8. Workflow-Integration mit n8n
• Webhook-Aufruf http://n8n:5678/webhook/start-transcription.
• Retry-Logic und Timeout im Backend (Axios).
• Workflow-Status via /api/workflow/status.
• Fehler-/Timeout-Handling: Userfreundliche Meldungen.
9. Systemüberwachung
• health-Endpoint prüft DB & n8n (Connection Pool pg + HTTP-HEAD zu n8n).
• Frontend zeigt Verbindungsstatus (Badges/Icons).
• Logging & Alerts bei Fehlern.
10. Deployment & Konfiguration
• Umgebungsvariablen (.env):
	- POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, N8N_URL.
• Docker
	- Dockerfile (Multi-stage), docker-compose.yml Integration.
