# Implementierungskonzept: Ollama-Host aus Datenbank lesen

## Übersicht

Dieses Dokument beschreibt die Implementierung, um den Ollama-Host im xstexport-service nicht mehr aus der .env-Datei (`OLLAMA_BASE_URL`) zu lesen, sondern aus der Datenbank (Parameter `aws_host` aus der `transcription_settings` Tabelle) mit statischem Port 11434.

## Anforderungen

1. **Datenbank-Lesung**: Ollama-Host aus `transcription_settings` Tabelle lesen (Parameter: `aws_host`)
2. **URL-Zusammensetzung**: `http://{aws_host}:11434` (Port 11434 ist statisch)
3. **Startup**: Wert beim Service-Start aus der Datenbank laden
4. **Vor jeder Verwendung**: Wert vor jedem LLM-Service-Aufruf aus der Datenbank laden
5. **Fallback**: Wenn Wert nicht in DB vorhanden, auf Standard-Fallback zurückgreifen

## Architektur-Übersicht

```
xstexport-service
    ↓
DatabaseService (bereits vorhanden)
    ↓ SQL Query
PostgreSQL (n8n Datenbank)
    ↑ transcription_settings Tabelle
    (parameter='aws_host', value='...')
    ↓
get_ollama_config() - liest aus DB
    ↓
LLMService - verwendet base_url
```

## Aktuelle Verwendung von OLLAMA_BASE_URL

### Verwendungsstellen:

1. **`app/config/database.py`** - `get_ollama_config()`:
   - Liest `OLLAMA_BASE_URL` aus .env
   - Wird zurückgegeben als `base_url` im Dictionary

2. **`app/main.py`** - `startup_event()`:
   - Ruft `get_ollama_config()` auf
   - Erstellt `LLMService` mit der base_url
   - Prüft Ollama-Verfügbarkeit

3. **`app/services/db_service.py`** - `process_meeting_series_with_llm()`:
   - Ruft `get_ollama_config()` auf, falls kein `llm_service` übergeben wurde
   - Erstellt `LLMService` mit der base_url

## Implementierungsschritte

### 1. Datenbank-Funktion zum Lesen des AWS Host

**Datei**: `xstexport-service/app/services/db_service.py`

**Neue Methode in `DatabaseService` Klasse: `get_transcription_setting(parameter: str) -> str | None`**:
- Liest einen Setting-Wert aus der `transcription_settings` Tabelle
- Parameter: `parameter` (z.B. "aws_host")
- Rückgabe: `value` (String) oder `None` wenn nicht vorhanden
- Verwendet `self.engine` für die Datenbankverbindung
- SQL Query: `SELECT value FROM transcription_settings WHERE parameter = :parameter`

**Implementierung**:
```python
def get_transcription_setting(self, parameter: str) -> Optional[str]:
    """
    Liest einen Setting-Wert aus der transcription_settings Tabelle.
    
    Args:
        parameter: Name des Parameters (z.B. "aws_host")
    
    Returns:
        Wert des Parameters oder None wenn nicht vorhanden
    """
    try:
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT value FROM transcription_settings WHERE parameter = :parameter"),
                {"parameter": parameter}
            )
            row = result.fetchone()
            if row:
                return row[0]
            return None
    except SQLAlchemyError as e:
        logger.warning(f"Fehler beim Lesen des Settings '{parameter}': {str(e)}")
        return None
```

### 2. Anpassung der get_ollama_config() Funktion

**Datei**: `xstexport-service/app/config/database.py`

**Änderungen**:
- Funktion erhält optionalen Parameter `db_service: Optional[DatabaseService] = None`
- Wenn `db_service` übergeben wird:
  1. Versuche `aws_host` aus der Datenbank zu lesen
  2. Falls vorhanden: Baue URL als `http://{aws_host}:11434`
  3. Falls nicht vorhanden: Fallback auf `.env` oder Standard
- Wenn `db_service` nicht übergeben wird (für Rückwärtskompatibilität):
  - Verhalte sich wie bisher (liest aus .env)

**Implementierung**:
```python
def get_ollama_config(db_service: Optional[DatabaseService] = None) -> Dict[str, str]:
    """
    Gibt die Ollama-Konfiguration zurück.
    Liest aws_host aus der Datenbank, falls db_service übergeben wird.
    
    Args:
        db_service: Optionaler DatabaseService zum Lesen aus der DB
    
    Returns:
        Dictionary mit 'base_url' und 'model'
    """
    base_url = None
    
    # Versuche zuerst aus Datenbank zu lesen
    if db_service is not None:
        try:
            aws_host = db_service.get_transcription_setting("aws_host")
            if aws_host:
                # Entferne http:// oder https:// falls vorhanden
                aws_host = aws_host.replace("http://", "").replace("https://", "").strip()
                # Entferne Port falls vorhanden
                if ":" in aws_host:
                    aws_host = aws_host.split(":")[0]
                base_url = f"http://{aws_host}:11434"
                logger.info(f"Ollama-Host aus Datenbank gelesen: {base_url}")
        except Exception as e:
            logger.warning(f"Fehler beim Lesen des aws_host aus der DB: {str(e)}, verwende Fallback")
    
    # Fallback auf .env oder Standard
    if base_url is None:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        logger.info(f"Ollama-Host aus .env/Standard verwendet: {base_url}")
    
    return {
        "base_url": base_url,
        "model": os.getenv("OLLAMA_MODEL", "phi4-mini:3.8b")
    }
```

**Import hinzufügen**:
```python
from typing import Optional
from app.services.db_service import DatabaseService
```

### 3. Anpassung der startup_event() Funktion

**Datei**: `xstexport-service/app/main.py`

**Änderungen**:
- `get_ollama_config()` wird mit `db_service` Parameter aufgerufen
- Sicherstellt, dass der Wert beim Startup aus der Datenbank geladen wird

**Implementierung**:
```python
@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Anwendung gestartet")
        # Tabelle erstellen, falls sie noch nicht existiert
        db_service.create_table_if_not_exists()
        
        # Prüfe Ollama-Verfügbarkeit (nicht-blockierend)
        try:
            from app.services.llm_service import LLMService
            ollama_config = get_ollama_config(db_service)  # db_service übergeben
            llm_service = LLMService(ollama_config['base_url'], ollama_config['model'])
            is_available, message = await llm_service.check_availability()
            if is_available:
                logger.info(f"✅ Ollama-Prüfung erfolgreich: {message}")
            else:
                logger.warning(f"⚠️ Ollama-Prüfung fehlgeschlagen: {message}")
        except Exception as e:
            logger.warning(f"⚠️ Ollama-Prüfung konnte nicht durchgeführt werden: {str(e)}")
            # Container startet trotzdem weiter
        
    except Exception as e:
        logger.error(f"Fehler beim Start: {str(e)}")
        raise
```

### 4. Anpassung der process_meeting_series_with_llm() Funktion

**Datei**: `xstexport-service/app/services/db_service.py`

**Änderungen**:
- `get_ollama_config()` wird mit `self` (DatabaseService) aufgerufen
- Sicherstellt, dass der Wert vor jedem LLM-Service-Aufruf aus der Datenbank geladen wird

**Implementierung**:
```python
async def process_meeting_series_with_llm(
    self, 
    table_name: str = "calendar_data",
    llm_service: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Orchestriert die gesamte LLM-Verarbeitung für Meeting-Series.
    
    Args:
        table_name: Name der Tabelle (Standard: "calendar_data")
        llm_service: Optionaler LLMService (wird erstellt falls None)
    
    Returns:
        Dictionary mit Statistik (total, success, failed)
    """
    if llm_service is None:
        from app.services.llm_service import LLMService
        from app.config.database import get_ollama_config
        ollama_config = get_ollama_config(self)  # self (DatabaseService) übergeben
        llm_service = LLMService(ollama_config['base_url'], ollama_config['model'])
    
    # ... rest der Funktion bleibt unverändert
```

**Import hinzufügen** (falls noch nicht vorhanden):
```python
from app.config.database import get_ollama_config
```

### 5. URL-Validierung und -Bereinigung

**Zusätzliche Validierung in `get_ollama_config()`**:
- Entferne `http://` oder `https://` Präfixe falls vorhanden
- Entferne Port falls in `aws_host` enthalten (z.B. "192.168.1.100:8080" → "192.168.1.100")
- Validiere, dass der Wert nicht leer ist
- Füge statisch Port 11434 hinzu

**Beispiele**:
- DB-Wert: `"192.168.1.100"` → URL: `"http://192.168.1.100:11434"`
- DB-Wert: `"http://192.168.1.100"` → URL: `"http://192.168.1.100:11434"`
- DB-Wert: `"192.168.1.100:8080"` → URL: `"http://192.168.1.100:11434"` (Port wird ignoriert)
- DB-Wert: `"ec2-xxx.amazonaws.com"` → URL: `"http://ec2-xxx.amazonaws.com:11434"`

## Datenfluss

### Beim Service-Start
1. `startup_event()` wird aufgerufen
2. `db_service` ist bereits initialisiert
3. `get_ollama_config(db_service)` wird aufgerufen
4. `db_service.get_transcription_setting("aws_host")` liest Wert aus DB
5. URL wird zusammengesetzt: `http://{aws_host}:11434`
6. `LLMService` wird mit der URL erstellt
7. Ollama-Verfügbarkeit wird geprüft

### Vor jedem LLM-Aufruf
1. `process_meeting_series_with_llm()` wird aufgerufen
2. Falls kein `llm_service` übergeben:
  3. `get_ollama_config(self)` wird aufgerufen (mit `self` als DatabaseService)
  4. Wert wird erneut aus DB gelesen (für aktuelle Werte)
  5. URL wird zusammengesetzt
  6. `LLMService` wird erstellt

## Fehlerbehandlung

### Datenbank-Fehler
- **Tabelle existiert nicht**: Fallback auf .env oder Standard
- **Parameter nicht gefunden**: Fallback auf .env oder Standard
- **Verbindungsfehler**: Fallback auf .env oder Standard
- Alle Fehler werden geloggt, aber Service startet weiter

### URL-Validierung
- **Leerer Wert**: Fallback auf .env oder Standard
- **Ungültiges Format**: Bereinigung (Entfernen von http://, Port, etc.)
- **Keine Verbindung möglich**: Fehler wird beim LLM-Service-Aufruf auftreten

## Rückwärtskompatibilität

- Wenn `db_service` nicht übergeben wird, verhält sich `get_ollama_config()` wie bisher
- Fallback auf `.env` Variable `OLLAMA_BASE_URL` bleibt erhalten
- Bestehende Aufrufe ohne `db_service` Parameter funktionieren weiterhin

## Logging

- Info-Log: Wenn Wert aus Datenbank gelesen wird
- Info-Log: Wenn Fallback auf .env/Standard verwendet wird
- Warning-Log: Bei Fehlern beim Lesen aus der Datenbank
- Alle Logs sollten den verwendeten Wert enthalten (ohne Passwörter)

## Abhängigkeiten

- **Keine neuen Dependencies erforderlich**
- `DatabaseService` hat bereits Zugriff auf `self.engine`
- SQLAlchemy ist bereits vorhanden
- Die `transcription_settings` Tabelle wird bereits vom Processing Service erstellt

## Implementierungsreihenfolge

1. ✅ **Schritt 1**: `get_transcription_setting()` Methode in `DatabaseService` hinzufügen
2. ✅ **Schritt 2**: `get_ollama_config()` Funktion anpassen (mit `db_service` Parameter)
3. ✅ **Schritt 3**: `startup_event()` anpassen (db_service übergeben)
4. ✅ **Schritt 4**: `process_meeting_series_with_llm()` anpassen (self übergeben)

## Zusammenfassung

Diese Implementierung ermöglicht es, den Ollama-Host dynamisch aus der Datenbank zu lesen, anstatt aus der .env-Datei. Der Wert wird beim Service-Start und vor jedem LLM-Aufruf aus der Datenbank geladen, um sicherzustellen, dass immer der aktuelle Wert verwendet wird. Die Lösung ist rückwärtskompatibel und hat einen Fallback-Mechanismus für den Fall, dass der Wert nicht in der Datenbank vorhanden ist.

