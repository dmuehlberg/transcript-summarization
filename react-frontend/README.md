# Transkriptions-Steuerung

Eine moderne React-basierte Single-Page-Application zur Verwaltung und Steuerung von Audio-Transkriptionen mit n8n-Workflow-Integration.

## 🚀 Features

- **Transkriptions-Dashboard**: Übersicht aller Transkriptionen mit Filterung und Suche
- **Inline-Editing**: Direkte Bearbeitung der Spracheinstellungen
- **Kalender-Integration**: Verknüpfung von Transkriptionen mit Kalender-Einträgen
- **Workflow-Steuerung**: Start und Überwachung von n8n-Workflows
- **Live-Updates**: Polling für Echtzeit-Updates der Tabellen und Workflow-Status
- **Responsive Design**: Moderne UI mit Shadcn/ui und Tailwind CSS
- **Docker-Support**: Vollständige Containerisierung

## 🏗️ Architektur

```
react-frontend/
├── src/
│   ├── components/          # React-Komponenten
│   │   ├── ui/             # Shadcn/ui Komponenten
│   │   ├── TranscriptionTable.tsx
│   │   ├── CalendarTable.tsx
│   │   ├── WorkflowControls.tsx
│   │   └── StatusBadge.tsx
│   ├── lib/                # Utilities und API
│   │   ├── api.ts          # API-Client
│   │   ├── types.ts        # TypeScript Typen
│   │   ├── data-formatters.ts
│   │   └── utils.ts
│   ├── App.tsx             # Haupt-App-Komponente
│   └── main.tsx            # App-Einstiegspunkt
├── server/                 # Express-Backend
│   ├── server.js           # API-Server
│   └── package.json
├── docker-compose.yml      # Docker-Compose
├── Dockerfile              # Frontend-Container
└── nginx.conf              # Nginx-Konfiguration
```

## 🛠️ Technologie-Stack

### Frontend
- **React 18** mit TypeScript
- **Vite** als Build-Tool
- **TanStack Table v8** für Tabellen
- **TanStack Query** für Server-State Management
- **Shadcn/ui** für UI-Komponenten
- **Tailwind CSS** für Styling
- **Lucide React** für Icons

### Backend
- **Node.js** mit Express
- **PostgreSQL** mit pg-Pool
- **Winston** für Logging
- **Axios** für HTTP-Requests

### DevOps
- **Docker** & Docker Compose
- **Nginx** als Reverse Proxy
- **PostgreSQL** Container

## 📋 API-Endpunkte

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/transcriptions` | GET | Liste aller Transkriptionen |
| `/api/transcriptions` | DELETE | Löscht mehrere Transkriptionen |
| `/api/transcriptions/:id/language` | PATCH | Aktualisiert Sprache |
| `/api/transcriptions/:id/link-calendar` | POST | Verknüpft Kalenderdaten |
| `/api/calendar` | GET | Kalenderdaten nach Datum |
| `/api/workflow/start` | POST | Startet n8n-Workflow |
| `/api/workflow/status` | GET | Workflow-Status |
| `/api/health` | GET | System-Health-Check |

## 🚀 Installation & Setup

### Voraussetzungen
- Docker & Docker Compose
- Node.js 18+ (für lokale Entwicklung)

### 1. Repository klonen
```bash
git clone <repository-url>
cd react-frontend
```

### 2. Umgebungsvariablen konfigurieren
```bash
cp env.example .env
# Bearbeite .env mit deinen Werten
```

### 3. Mit Docker starten
```bash
# Alle Services starten (im Hauptverzeichnis)
cd ..
docker-compose up -d

# Nur React-Services starten
docker-compose up -d react-frontend react-backend

# Datenbank-Tabellen einrichten
cd react-frontend
./setup_database.sh
```

### 4. Lokale Entwicklung
```bash
# Frontend Dependencies installieren
npm install

# Backend Dependencies installieren
cd server && npm install

# Frontend starten (Port 8401)
npm run dev

# Backend starten (Port 3002)
cd server && npm run dev
```

## 🌐 Zugriff

- **React Frontend**: http://localhost:8401
- **Express Backend API**: http://localhost:3002
- **Streamlit Frontend**: http://localhost:8400
- **n8n**: http://localhost:5678
- **PostgreSQL**: localhost:5432

## 📊 Datenbank-Schema

### Transkriptionen-Tabelle
```sql
CREATE TABLE transcriptions (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    transcription_status VARCHAR(50) DEFAULT 'pending',
    set_language VARCHAR(10) DEFAULT 'auto',
    meeting_title TEXT,
    meeting_start_date TIMESTAMP,
    participants TEXT,
    transcription_duration INTEGER,
    audio_duration INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    detected_language VARCHAR(10),
    transcript_text TEXT,
    corrected_text TEXT,
    recording_date TIMESTAMP
);
```

### Kalender-Einträge-Tabelle
```sql
CREATE TABLE calendar_entries (
    id SERIAL PRIMARY KEY,
    subject VARCHAR(255) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    location TEXT,
    attendees TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 Konfiguration

### Umgebungsvariablen

| Variable | Beschreibung | Standard |
|----------|--------------|----------|
| `VITE_API_URL` | API-Basis-URL | `http://localhost:8400/api` |
| `POSTGRES_HOST` | PostgreSQL Host | `localhost` |
| `POSTGRES_PORT` | PostgreSQL Port | `5432` |
| `POSTGRES_DB` | Datenbankname | `transcript_db` |
| `POSTGRES_USER` | Datenbankbenutzer | `postgres` |
| `POSTGRES_PASSWORD` | Datenbankpasswort | `password` |
| `N8N_URL` | n8n-URL | `http://n8n:5678` |
| `N8N_API_KEY` | n8n API-Schlüssel | - |

## 🎨 UI-Komponenten

### TranscriptionTable
- TanStack Table mit Sortierung, Filterung und Pagination
- Inline-Editing für Spracheinstellungen
- Mehrfachauswahl für Batch-Operationen
- Live-Updates alle 10 Sekunden

### CalendarTable
- Kalender-Einträge nach Datum gefiltert
- Verknüpfung mit Transkriptionen
- Responsive Design

### WorkflowControls
- Workflow-Start-Button
- Live-Status-Anzeige
- Health-Check für Datenbank und n8n
- Polling alle 5 Sekunden

## 🔄 Workflow-Integration

Die Anwendung integriert sich mit n8n über:
- **Webhook**: `POST /webhook/start-transcription`
- **API**: Status-Abfrage über n8n REST API
- **Health-Check**: Verfügbarkeitsprüfung

## 🐛 Troubleshooting

### Häufige Probleme

1. **Datenbank-Verbindung fehlschlägt**
   ```bash
   # PostgreSQL-Container Status prüfen
   docker-compose ps postgres
   
   # Logs anzeigen
   docker-compose logs postgres
   ```

2. **n8n nicht erreichbar**
   ```bash
   # n8n-Container starten
   docker-compose --profile n8n up -d n8n
   
   # Health-Check
   curl http://localhost:5678/health
   ```

3. **Frontend lädt nicht**
   ```bash
   # Build-Status prüfen
   docker-compose logs frontend
   
   # Nginx-Konfiguration testen
   docker-compose exec frontend nginx -t
   ```

## 📝 Entwicklung

### Code-Struktur
- **TypeScript** für Typsicherheit
- **ESLint** für Code-Qualität
- **Prettier** für Formatierung
- **Husky** für Git-Hooks (optional)

### Testing
```bash
# Frontend Tests
npm run test

# Backend Tests
cd server && npm test
```

### Build
```bash
# Production Build
npm run build

# Docker Build
docker-compose build
```

## 📄 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert.

## 🤝 Beitragen

1. Fork das Repository
2. Erstelle einen Feature-Branch
3. Committe deine Änderungen
4. Push zum Branch
5. Erstelle einen Pull Request

## 📞 Support

Bei Fragen oder Problemen:
- Erstelle ein Issue im Repository
- Kontaktiere das Entwicklungsteam
- Prüfe die Dokumentation 