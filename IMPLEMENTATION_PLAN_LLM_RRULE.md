# Implementierungskonzept: LLM-basierte RRULE-Konvertierung für Meeting-Series

## Übersicht

Dieses Dokument beschreibt die Implementierung einer automatischen Konvertierung von natürlichen Serientermin-Beschreibungen (aus `meeting_series_rhythm`, `meeting_series_start_date`, `meeting_series_end_date`) in strukturierte RRULE-Felder mittels Ollama LLM (phi4-mini:3.8b).

## Architektur-Übersicht

```
CSV-Import → DB-Import → LLM-Verarbeitung → DB-Update
     ↓            ↓              ↓              ↓
calendar_data  calendar_data  Ollama API   calendar_data
                              (phi4-mini:3.8b)    (erweiterte Felder)
```

## 1. Konfiguration

### 1.1 .env-Datei erweitern

**Datei:** `/Volumes/Samsung 512GB/transcript-summarization/.env`

**Hinzuzufügen:**
```env
# Ollama LLM Konfiguration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=phi4-mini:3.8b
```

**Begründung:**
- Flexibel für lokale und AWS-Instanzen
- Modellname konfigurierbar für zukünftige Änderungen

### 1.2 requirements.txt erweitern

**Datei:** `/Volumes/Samsung 512GB/transcript-summarization/xstexport-service/requirements.txt`

**Hinzuzufügen:**
```
# Für Ollama LLM API-Aufrufe
ollama>=0.1.0
```

**Alternative:** Falls `ollama`-Paket nicht verfügbar, verwende `httpx` (bereits vorhanden) für direkte HTTP-Requests.

## 2. Neue Service-Klasse: LLMService

### 2.1 Datei-Struktur

**Neue Datei:** `/Volumes/Samsung 512GB/transcript-summarization/xstexport-service/app/services/llm_service.py`

**Zweck:**
- Kapselung aller LLM-Interaktionen
- System-Prompt-Verwaltung
- JSON-Parsing und Validierung
- Fehlerbehandlung und Retry-Logik

### 2.2 Klassen-Design

```python
class LLMService:
    def __init__(self, ollama_base_url: str, model: str = "phi4-mini:3.8b")
    async def parse_meeting_series(self, rhythm: str, start_date: str, end_date: str) -> Dict[str, Any]
    def _build_system_prompt(self) -> str
    def _build_user_prompt(self, rhythm: str, start_date: str, end_date: str) -> str
    async def _call_ollama(self, system_prompt: str, user_prompt: str) -> str
    def _parse_json_response(self, response: str) -> Dict[str, Any]
    def _validate_rrule_fields(self, data: Dict[str, Any]) -> Dict[str, Any]
```

### 2.3 System-Prompt

**Speicherung:** Als Klassenmethode oder Konstante in `llm_service.py`

**Inhalt:** (wie vom Benutzer spezifiziert)
- Deterministischer Parser-Ansatz
- JSON-Schema-Definition
- Konvertierungsregeln
- Few-shot Beispiele

### 2.4 User-Prompt-Format

**Struktur:**
```
Input: "{rhythm_text}"
Start Date: {start_date}
End Date: {end_date}
```

**Beispiel:**
```
Input: "every Monday, Wednesday, and Friday from 14:00 to 14:30"
Start Date: 2025-11-10T14:00:00+01:00
End Date: 2025-11-10T14:30:00+01:00
```

### 2.5 API-Aufruf-Format

**Ollama API-Endpoint:** `POST {ollama_base_url}/api/generate`

**Request-Body:**
```json
{
  "model": "phi4-mini:3.8b",
  "system": "<system_prompt>",
  "prompt": "<user_prompt>",
  "stream": false,
  "format": "json"
}
```

**Response:** JSON-Objekt mit RRULE-Feldern

### 2.6 Fehlerbehandlung

- **Timeout:** 30 Sekunden pro Request
- **Retry:** Max. 3 Versuche bei Netzwerkfehlern
- **JSON-Parsing-Fehler:** Logging + Fallback auf leere Werte
- **Validierungsfehler:** Korrektur wo möglich, sonst Logging

## 3. Erweiterung DatabaseService

### 3.1 Neue Methoden in db_service.py

**Datei:** `/Volumes/Samsung 512GB/transcript-summarization/xstexport-service/app/services/db_service.py`

#### 3.1.1 Methode: `get_rows_with_meeting_series`

```python
def get_rows_with_meeting_series(self, table_name: str = "calendar_data") -> List[Dict[str, Any]]
```

**Zweck:**
- Abrufen aller Zeilen mit gefülltem `meeting_series_rhythm`
- Rückgabe als Liste von Dictionaries mit `id`, `meeting_series_rhythm`, `meeting_series_start_date`, `meeting_series_end_date`

**SQL-Query:**
```sql
SELECT id, meeting_series_rhythm, meeting_series_start_date, meeting_series_end_date
FROM calendar_data
WHERE meeting_series_rhythm IS NOT NULL 
  AND meeting_series_rhythm != ''
  AND (meeting_series_start_time IS NULL OR meeting_series_end_time IS NULL)
```

**Hinweis:** Nur Zeilen verarbeiten, bei denen die neuen Felder noch nicht gefüllt sind (idempotent).

#### 3.1.2 Methode: `update_meeting_series_fields`

```python
def update_meeting_series_fields(
    self, 
    row_id: int, 
    rrule_data: Dict[str, Any], 
    table_name: str = "calendar_data"
) -> None
```

**Zweck:**
- Update einer einzelnen Zeile mit den LLM-generierten RRULE-Feldern
- Konvertierung von Python-Datentypen zu PostgreSQL-kompatiblen Werten

**SQL-Update:**
```sql
UPDATE calendar_data
SET 
    meeting_series_start_time = :start_time,
    meeting_series_end_time = :end_time,
    meeting_series_frequency = :frequency,
    meeting_series_interval = :interval,
    meeting_series_weekdays = :weekdays,
    meeting_series_monthday = :monthday,
    meeting_series_weekday_nth = :weekday_nth,
    meeting_series_months = :months,
    meeting_series_exceptions = :exceptions
WHERE id = :id
```

**Datentyp-Konvertierung:**
- `timestamp with time zone`: ISO 8601 String → PostgreSQL TIMESTAMP
- `INTEGER`: Python int → PostgreSQL INTEGER (NULL-Handling)
- `text`: Python str → PostgreSQL TEXT (NULL-Handling)

### 3.2 Erweiterung: `import_csv_to_db`

**Datei:** `/Volumes/Samsung 512GB/transcript-summarization/xstexport-service/app/services/db_service.py`

**Änderung:** Am Ende der Methode `import_csv_to_db` (nach Zeile 197) einen Aufruf zur LLM-Verarbeitung hinzufügen:

```python
# Nach erfolgreichem CSV-Import: LLM-Verarbeitung starten
try:
    self.process_meeting_series_with_llm(table_name)
except Exception as e:
    logger.warning(f"LLM-Verarbeitung fehlgeschlagen, aber CSV-Import erfolgreich: {str(e)}")
    # Nicht als kritischer Fehler behandeln
```

**Begründung:**
- CSV-Import soll auch bei LLM-Fehlern erfolgreich sein
- LLM-Verarbeitung als optionaler Post-Processing-Schritt

#### 3.1.3 Methode: `process_meeting_series_with_llm`

```python
async def process_meeting_series_with_llm(
    self, 
    table_name: str = "calendar_data",
    llm_service: Optional[LLMService] = None
) -> Dict[str, Any]
```

**Zweck:**
- Orchestriert die gesamte LLM-Verarbeitung
- Ruft `get_rows_with_meeting_series` auf
- Verarbeitet jede Zeile asynchron mit `LLMService`
- Aktualisiert Datenbank mit `update_meeting_series_fields`
- Gibt Statistik zurück (verarbeitet, erfolgreich, fehlgeschlagen)

**Implementierung:**
```python
async def process_meeting_series_with_llm(self, table_name: str = "calendar_data", llm_service: Optional[LLMService] = None) -> Dict[str, Any]:
    if llm_service is None:
        from app.services.llm_service import LLMService
        from app.config.database import get_ollama_config
        ollama_config = get_ollama_config()
        llm_service = LLMService(ollama_config['base_url'], ollama_config['model'])
    
    rows = self.get_rows_with_meeting_series(table_name)
    stats = {'total': len(rows), 'success': 0, 'failed': 0}
    
    for row in rows:
        try:
            rrule_data = await llm_service.parse_meeting_series(
                row['meeting_series_rhythm'],
                row['meeting_series_start_date'],
                row['meeting_series_end_date']
            )
            self.update_meeting_series_fields(row['id'], rrule_data, table_name)
            stats['success'] += 1
        except Exception as e:
            logger.error(f"Fehler bei LLM-Verarbeitung für Zeile {row['id']}: {str(e)}")
            stats['failed'] += 1
    
    return stats
```

**Hinweis:** Da `db_service.py` synchron ist, muss die Methode `process_meeting_series_with_llm` als `async` deklariert werden. Der Aufruf in `import_csv_to_db` muss dann mit `asyncio.run()` oder ähnlich erfolgen.

## 4. Konfiguration erweitern

### 4.1 Neue Funktion in database.py

**Datei:** `/Volumes/Samsung 512GB/transcript-summarization/xstexport-service/app/config/database.py`

**Hinzuzufügen:**
```python
def get_ollama_config():
    """Gibt die Ollama-Konfiguration zurück."""
    return {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "model": os.getenv("OLLAMA_MODEL", "phi4-mini:3.8b")
    }
```

## 5. Integration in main.py

### 5.1 Endpoint erweitern

**Datei:** `/Volumes/Samsung 512GB/transcript-summarization/xstexport-service/app/main.py`

**Änderung:** Im Endpoint `/import-calendar-csv` (Zeile 341-410) nach erfolgreichem Import:

```python
# CSV-Datei in die Datenbank importieren
logger.info(f"Importiere CSV-Datei in Tabelle: {table_name} mit Quelle: {source}")
db_service.import_csv_to_db(temp_file_path, table_name, source)

# LLM-Verarbeitung für Meeting-Series starten
try:
    import asyncio
    stats = await db_service.process_meeting_series_with_llm(table_name)
    logger.info(f"LLM-Verarbeitung abgeschlossen: {stats}")
except Exception as e:
    logger.warning(f"LLM-Verarbeitung fehlgeschlagen: {str(e)}")
    # Nicht als kritischer Fehler behandeln

logger.info("CSV-Import erfolgreich abgeschlossen")
```

**Hinweis:** Da FastAPI-Endpoints async sind, kann `await` direkt verwendet werden.

### 5.2 Neuer Endpoint (optional)

**Endpoint:** `POST /process-meeting-series`

**Zweck:**
- Manuelle Auslösung der LLM-Verarbeitung
- Nützlich für Re-Processing oder nach manuellen DB-Updates

**Implementierung:**
```python
@app.post("/process-meeting-series")
async def process_meeting_series(
    table_name: str = Form("calendar_data", description="Name der Tabelle")
):
    """
    Verarbeitet alle Zeilen mit meeting_series_rhythm mittels LLM.
    """
    try:
        stats = await db_service.process_meeting_series_with_llm(table_name)
        return JSONResponse(
            content={
                "status": "success",
                "message": "LLM-Verarbeitung abgeschlossen",
                "statistics": stats
            }
        )
    except Exception as e:
        logger.error(f"Fehler bei LLM-Verarbeitung: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Fehler bei LLM-Verarbeitung: {str(e)}"
        )
```

## 6. Datenvalidierung und -konvertierung

### 6.1 Timestamp-Konvertierung

**Problem:** LLM gibt ISO 8601 Strings zurück, PostgreSQL benötigt TIMESTAMP WITH TIME ZONE

**Lösung:**
```python
from datetime import datetime
import pytz

def convert_to_timestamp(value: Optional[str], default_tz: str = "Europe/Berlin") -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            tz = pytz.timezone(default_tz)
            dt = tz.localize(dt)
        return dt
    except Exception as e:
        logger.error(f"Fehler bei Timestamp-Konvertierung: {str(e)}")
        return None
```

### 6.2 Integer-Konvertierung

**Problem:** LLM gibt möglicherweise Strings zurück, PostgreSQL benötigt INTEGER

**Lösung:**
```python
def convert_to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
```

### 6.3 Text-Konvertierung

**Problem:** NULL-Handling für Text-Felder

**Lösung:**
```python
def convert_to_text(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value).strip()
```

## 7. Fehlerbehandlung und Logging

### 7.1 Logging-Strategie

- **INFO:** Start/Ende der LLM-Verarbeitung, Statistik
- **WARNING:** Einzelne Zeilen-Fehler, LLM-Timeout
- **ERROR:** Kritische Fehler (DB-Verbindung, JSON-Parsing)

### 7.2 Fehlerbehandlung

- **LLM nicht erreichbar:** Warning loggen, CSV-Import trotzdem erfolgreich
- **Einzelne Zeile fehlgeschlagen:** Weiter mit nächster Zeile
- **JSON-Parsing fehlgeschlagen:** Fallback auf leere Werte, Zeile überspringen

## 8. Testing-Strategie

### 8.1 Unit-Tests

- `LLMService._parse_json_response()` mit verschiedenen JSON-Formaten
- `LLMService._validate_rrule_fields()` mit validen/invaliden Daten
- Datentyp-Konvertierungen

### 8.2 Integration-Tests

- Mock Ollama API für deterministische Tests
- End-to-End Test mit Test-CSV-Datei
- Fehlerbehandlung bei LLM-Ausfall

### 8.3 Manuelle Tests

- CSV-Import mit verschiedenen `meeting_series_rhythm`-Formaten
- Überprüfung der generierten RRULE-Felder in der Datenbank
- Test mit lokalem und remote Ollama

## 9. Performance-Überlegungen

### 9.1 Batch-Verarbeitung

- **Aktuell:** Sequenzielle Verarbeitung (eine Zeile nach der anderen)
- **Zukunft:** Batch-Processing für mehrere Zeilen gleichzeitig (asyncio.gather)

### 9.2 Caching

- **Optional:** Cache für identische `meeting_series_rhythm`-Werte
- **Speicherung:** In-Memory oder Redis

### 9.3 Timeout-Handling

- **LLM-Request-Timeout:** 30 Sekunden
- **Gesamt-Timeout:** Kein Limit (kann bei vielen Zeilen lange dauern)

## 10. Implementierungsreihenfolge

1. ✅ **Konfiguration erweitern** (.env, database.py)
2. ✅ **LLMService erstellen** (llm_service.py)
3. ✅ **DatabaseService erweitern** (get_rows, update_fields, process_meeting_series)
4. ✅ **main.py integrieren** (automatischer Aufruf nach CSV-Import)
5. ✅ **Testing** (manuelle Tests mit echten Daten)
6. ✅ **Dokumentation** (README aktualisieren)

## 11. Abhängigkeiten

### 11.1 Neue Python-Pakete

- `ollama` (falls verfügbar) oder `httpx` (bereits vorhanden)
- Keine weiteren Abhängigkeiten nötig

### 11.2 Externe Services

- Ollama-Container muss laufen (Port 11434)
- phi4-mini:3.8b Modell muss in Ollama verfügbar sein

## 12. Rollback-Strategie

- **Bei Fehlern:** CSV-Import bleibt erfolgreich, nur LLM-Verarbeitung schlägt fehl
- **Manuelle Korrektur:** Über SQL möglich
- **Re-Processing:** Über `/process-meeting-series` Endpoint

## 13. Monitoring

### 13.1 Metriken

- Anzahl verarbeiteter Zeilen
- Erfolgsrate
- Durchschnittliche Verarbeitungszeit pro Zeile
- LLM-API-Fehlerrate

### 13.2 Logging

- Strukturierte Logs für einfache Analyse
- Fehler-IDs für Tracking

## 14. Zukünftige Erweiterungen

- **Batch-Processing:** Mehrere Zeilen parallel verarbeiten
- **Caching:** Identische Rhythm-Werte cachen
- **Alternative LLMs:** Unterstützung für andere Modelle
- **Inkrementelle Updates:** Nur neue/geänderte Zeilen verarbeiten
- **Webhook-Integration:** Benachrichtigung nach Abschluss

