# Streamlit Transcription Service Dashboard

Eine moderne Streamlit-App mit AG-Grid zur Steuerung des Transcription Services. Die App kommuniziert mit der n8n PostgreSQL-Datenbank und dem n8n Workflow-Service.

## 🚀 Features

- **Moderne UI**: Streamlit mit AG-Grid für beste Benutzererfahrung
- **Datenbankintegration**: Direkte Verbindung zur n8n PostgreSQL-Datenbank
- **Workflow-Steuerung**: n8n Workflows über HTTP-API triggern
- **Editierbare Tabellen**: Direkte Bearbeitung von Sprachen in AG-Grid
- **Navigation**: Flüssige Navigation zwischen zwei Screens
- **Error Handling**: Robuste Fehlerbehandlung für alle externen Dependencies
- **Responsive Design**: Modernes, benutzerfreundliches Design

## 📋 Anforderungen

- Python 3.9+
- Docker & Docker Compose
- PostgreSQL (n8n Container)
- n8n Workflow Service

## 🛠️ Installation

### 1. Projektstruktur

```
streamlit-frontend/
├── Dockerfile
├── requirements.txt
├── app.py
├── database.py
├── components/
│   ├── __init__.py
│   ├── transcriptions_screen.py
│   └── calendar_screen.py
├── utils/
│   ├── __init__.py
│   ├── db_utils.py
│   └── workflow_utils.py
├── tests/
│   ├── __init__.py
│   ├── test_database.py
│   └── test_workflow.py
└── README.md
```

### 2. Umgebungsvariablen

Erstellen Sie eine `.env` Datei im Projektroot:

```env
POSTGRES_HOST=n8n
POSTGRES_DB=n8n
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
POSTGRES_PORT=5432
```

### 3. Docker Setup

```bash
# Container bauen und starten
docker build -t streamlit-dashboard .
docker run -p 8400:8400 --env-file .env streamlit-dashboard
```

### 4. Lokale Entwicklung

```bash
# Dependencies installieren
pip install -r requirements.txt

# App starten
streamlit run app.py --server.port=8400
```

## 🎯 Verwendung

### Screen 1: Transkriptionen Dashboard

- **Refresh Table**: Lädt die AG-Grid Tabelle neu aus der Datenbank
- **Start Transcription Workflow**: HTTP GET Request an `http://n8n:5678/webhook/start-transcription`
- **AG-Grid Tabelle**: 
  - Alle Spalten aus `n8n.transcriptions`
  - `set_language` Spalte ist direkt editierbar
  - "Select Meeting" Button in jeder Zeile
  - Paginierung und Sortierung

### Screen 2: Kalenderauswahl

- **Filter**: Zeigt nur `calendar_data` Einträge mit matching `start_date`
- **Back Button**: Zurück zu Screen 1
- **Select Button**: Überträgt Meeting-Daten in `transcriptions` Tabelle

## 🗄️ Datenbank-Schema

### Tabelle: n8n.transcriptions
```sql
- id (Primary Key)
- filename
- transcription_status
- set_language (editierbar)
- meeting_title
- meeting_start_date
- participants
- transcription_duration
- audio_duration
- created_at
- detected_language
- transcript_text
- corrected_text
- recording_date
```

### Tabelle: n8n.calendar_data
```sql
- subject
- start_date
- (weitere Felder je nach Schema)
```

## 🧪 Testing

### Unit Tests ausführen

```bash
# Alle Tests
pytest

# Mit Coverage
pytest --cov=. --cov-report=html

# Spezifische Tests
pytest tests/test_database.py
pytest tests/test_workflow.py
```

### Test-Coverage

```bash
# Coverage-Report generieren
pytest --cov=. --cov-report=html --cov-report=term-missing
```

## 🎨 UI/UX Design

### Farbschema
- **Primärfarbe**: #1f77b4 (Blau)
- **Sekundärfarbe**: #ff7f0e (Orange)
- **Hintergrund**: #f0f2f6 (Hellgrau)
- **Text**: #262730 (Dunkelgrau)

### Typografie
- **Überschriften**: Roboto, 24px, Bold
- **Body Text**: Roboto, 16px, Regular
- **Buttons**: Roboto, 14px, Medium

## 🔧 Konfiguration

### Docker Compose Integration

Fügen Sie den Service zur bestehenden `docker-compose.yml` hinzu:

```yaml
streamlit-dashboard:
  build: ./streamlit-frontend
  ports:
    - "8400:8400"
  environment:
    - POSTGRES_HOST=n8n
    - POSTGRES_DB=n8n
    - POSTGRES_USER=${POSTGRES_USER}
    - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    - POSTGRES_PORT=5432
  depends_on:
    - n8n
    - postgres
  networks:
    - n8n-network
```

### AG-Grid Konfiguration

```python
# Beispiel für editierbare Spalten
gb.configure_column("set_language", editable=True)

# Beispiel für Button-Renderer
gb.configure_column(
    "Select Meeting",
    cellRenderer="buttonRenderer",
    cellRendererParams={
        "buttonText": "Meeting auswählen",
        "style": {"backgroundColor": "#1f77b4"}
    }
)
```

## 🚨 Error Handling

### Datenbankfehler
- Connection Pooling mit automatischer Wiederherstellung
- Timeout-Handling für langsame Queries
- Rollback bei Transaktionsfehlern

### API-Fehler
- Retry-Logic für n8n API-Calls
- Timeout-Handling (30 Sekunden)
- Benutzerfreundliche Fehlermeldungen

### UI-Fehler
- Graceful Degradation bei fehlenden Daten
- Loading States für alle Operationen
- Informative Error Messages

## 📊 Performance

### Optimierungen
- Connection Pooling für Datenbankverbindungen
- AG-Grid Virtualisierung für große Datensätze
- Lazy Loading von Komponenten
- Caching von häufig verwendeten Daten

### Monitoring
- Logging für alle kritischen Operationen
- Performance-Metriken für Datenbankqueries
- Error-Tracking für API-Calls

## 🔒 Sicherheit

### Best Practices
- Umgebungsvariablen für sensible Daten
- Prepared Statements für SQL-Queries
- Input-Validierung für alle Benutzereingaben
- HTTPS für Produktionsumgebung

## 📝 Logging

### Log-Level
- **INFO**: Normale Operationen
- **WARNING**: Potentielle Probleme
- **ERROR**: Fehler mit Auswirkungen
- **DEBUG**: Detaillierte Debug-Informationen

### Log-Format
```
2024-01-01 10:00:00 - INFO - Transcription workflow started successfully
2024-01-01 10:00:01 - ERROR - Database connection failed: timeout
```

## 🤝 Beitragen

1. Fork das Repository
2. Erstellen Sie einen Feature-Branch
3. Implementieren Sie Ihre Änderungen
4. Fügen Sie Tests hinzu
5. Erstellen Sie einen Pull Request

## 📄 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert.

## 🆘 Support

Bei Fragen oder Problemen:

1. Überprüfen Sie die Logs
2. Testen Sie die Datenbankverbindung
3. Überprüfen Sie die n8n API-Verfügbarkeit
4. Erstellen Sie ein Issue im Repository

## 🔄 Updates

### Version 1.0.0
- Initiale Implementierung
- AG-Grid Integration
- Datenbankverbindung
- n8n Workflow-Integration
- Unit Tests
- Docker-Support 