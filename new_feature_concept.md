# Streamlit Transcription Service Dashboard - Implementierungskonzept

## Übersicht
Erstellung einer modernen Streamlit-App mit AG-Grid zur Steuerung des Transcription Services. Die App kommuniziert mit der n8n Postgres-Datenbank und dem n8n Workflow-Service.

## Technische Spezifikationen

### Container-Konfiguration
- **Docker Container**: Streamlit-App mit AG-Grid
- **Port**: 8400 (localhost)
- **Datenbank**: PostgreSQL (n8n Container)
- **Workflow-Service**: n8n Container (Port 5678)

### Abhängigkeiten
```python
streamlit
streamlit-aggrid
psycopg2-binary
python-dotenv
requests
pandas
```

## Datenbank-Schema

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

## App-Struktur

### Screen 1: Transcriptions (Startscreen)

#### Layout
```
┌─────────────────────────────────────────────────────────────┐
│                    TRANSCRIPTION DASHBOARD                   │
├─────────────────────────────────────────────────────────────┤
│  [🔄 Refresh Table]  [▶️ Start Transcription Workflow]       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    AG-GRID TABLE                        │ │
│  │  ┌─────┬─────────┬─────────┬─────────┬─────────┬──────┐ │ │
│  │  │File │Status   │Language │Title    │Start    │Select│ │ │
│  │  │Name │         │(edit)   │         │Date     │Meeting│ │ │
│  │  ├─────┼─────────┼─────────┼─────────┼─────────┼──────┤ │ │
│  │  │     │         │         │         │         │[Btn] │ │ │
│  │  └─────┴─────────┴─────────┴─────────┴─────────┴──────┘ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### Funktionalitäten
1. **Refresh Button**: Lädt die AG-Grid Tabelle neu aus der Datenbank
2. **Start Transcription Workflow Button**: 
   - HTTP GET Request an `http://n8n:5678/webhook/start-transcription`
   - Zeigt Erfolgs-/Fehlermeldung an
3. **AG-Grid Tabelle**:
   - Alle Spalten aus n8n.transcriptions
   - `set_language` Spalte ist direkt editierbar
   - Änderungen werden sofort in die Datenbank geschrieben
   - "Select Meeting" Button in jeder Zeile
   - Paginierung und Sortierung

### Screen 2: Calendar Entry Selection

#### Layout
```
┌─────────────────────────────────────────────────────────────┐
│              CALENDAR ENTRY SELECTION                       │
│  Meeting: [Meeting Title] | Date: [Start Date]             │
├─────────────────────────────────────────────────────────────┤
│  [← Back to Transcriptions]                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    AG-GRID TABLE                        │ │
│  │  ┌─────────┬─────────┬─────────┐                        │ │
│  │  │Subject  │Start    │Select   │                        │ │
│  │  │         │Date     │         │                        │ │
│  │  ├─────────┼─────────┼─────────┤                        │ │
│  │  │         │         │[Select] │                        │ │
│  │  └─────────┴─────────┴─────────┘                        │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### Funktionalitäten
1. **Filter**: Zeigt nur calendar_data Einträge mit matching start_date
2. **Back Button**: Zurück zu Screen 1
3. **Select Button**: 
   - REST-API Call (noch zu definieren)
   - Überträgt Meeting-Daten in transcriptions Tabelle
   - Zeigt Erfolgs-/Fehlermeldung an

## Implementierungsdetails

### 1. Docker Setup
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8400
CMD ["streamlit", "run", "app.py", "--server.port=8400", "--server.address=0.0.0.0"]
```

### 2. Datenbankverbindung
```python
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'n8n'),
        database=os.getenv('POSTGRES_DB', 'n8n'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        port=os.getenv('POSTGRES_PORT', 5432)
    )
```

### 3. AG-Grid Konfiguration
```python
from streamlit_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

def create_transcriptions_grid(df):
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_column("set_language", editable=True)
    gb.configure_column("Select Meeting", 
                       cellRenderer="buttonRenderer",
                       cellRendererParams={"buttonText": "Select Meeting"})
    gb.configure_grid_options(domLayout='normal')
    return gb.build()
```

### 4. Workflow-Integration
```python
import requests

def start_transcription_workflow():
    try:
        response = requests.get("http://n8n:5678/webhook/start-transcription")
        if response.status_code == 200:
            st.success("Transcription workflow started successfully!")
        else:
            st.error(f"Failed to start workflow: {response.status_code}")
    except Exception as e:
        st.error(f"Error connecting to n8n: {str(e)}")
```

### 5. State Management
```python
import streamlit as st

# Session State für Navigation
if 'current_screen' not in st.session_state:
    st.session_state.current_screen = 'transcriptions'

if 'selected_meeting_id' not in st.session_state:
    st.session_state.selected_meeting_id = None

if 'selected_start_date' not in st.session_state:
    st.session_state.selected_start_date = None
```

## Dateistruktur
```
streamlit-dashboard/
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
└── .env
```

## UI/UX Design Guidelines

### Farbschema
- **Primärfarbe**: #1f77b4 (Blau)
- **Sekundärfarbe**: #ff7f0e (Orange)
- **Hintergrund**: #f0f2f6 (Hellgrau)
- **Text**: #262730 (Dunkelgrau)

### Typografie
- **Überschriften**: Roboto, 24px, Bold
- **Body Text**: Roboto, 16px, Regular
- **Buttons**: Roboto, 14px, Medium

### Layout-Prinzipien
- Minimalistisches Design
- Ausreichend Whitespace
- Konsistente Abstände (16px, 24px, 32px)
- Responsive Design
- Klare visuelle Hierarchie

## Implementierungsschritte

1. **Docker Container Setup**
   - Dockerfile erstellen
   - requirements.txt definieren
   - docker-compose.yml erweitern

2. **Datenbankverbindung**
   - PostgreSQL Connection Pool
   - Error Handling
   - Connection Testing

3. **Screen 1: Transcriptions**
   - AG-Grid Integration
   - Editierbare Spalten
   - Button Integration
   - Workflow-Trigger

4. **Screen 2: Calendar Selection**
   - Filtered AG-Grid
   - Navigation
   - API Integration

5. **Styling & UX**
   - Custom CSS
   - Responsive Design
   - Loading States
   - Error Messages

6. **Testing & Deployment**
   - Unit Tests
   - Integration Tests
   - Docker Build
   - Deployment

## Nächste Schritte für Cursor

1. Erstelle die Dockerfile und requirements.txt
2. Implementiere die Hauptapp (app.py) mit Navigation
3. Erstelle die Datenbankverbindung (database.py)
4. Implementiere Screen 1 (transcriptions_screen.py)
5. Implementiere Screen 2 (calendar_screen.py)
6. Füge Styling und Error Handling hinzu
7. Teste die Integration mit n8n und PostgreSQL
8. Erweitere docker-compose.yml um den neuen Container

## Anmerkungen

- Die App soll robuste Error Handling für Datenbankverbindungen haben
- Alle API-Calls sollen mit Timeouts und Retry-Logic versehen sein
- Die AG-Grid Konfiguration soll performant für große Datensätze sein
- Das Design soll modern und benutzerfreundlich sein
- Die Navigation zwischen Screens soll flüssig sein
