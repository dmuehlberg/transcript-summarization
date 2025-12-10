# Implementierungskonzept: LLM-Provider-Erweiterung für xstexport-service

## Übersicht

Dieses Konzept beschreibt die Erweiterung des `xstexport-service` Containers, um neben OLLAMA auch OpenAI als LLM-Provider zu unterstützen. Die Funktionalität zur Konvertierung unstrukturierter Serientermin-Strings in JSON-Strukturen soll dabei für beide Provider verfügbar sein.

## Aktueller Stand

### Verwendete Komponenten

1. **LLMService** (`app/services/llm_service.py`)
   - Aktuell nur OLLAMA-Integration
   - Methode `_call_ollama()` für API-Requests
   - System-Prompt und User-Prompt werden aus externen Quellen geladen/erstellt
   - JSON-Parsing und Validierung der LLM-Responses

2. **Konfiguration** (`app/config/database.py`)
   - Funktion `get_ollama_config()` liest OLLAMA-Parameter aus .env
   - Unterstützte Parameter: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_NUM_CTX`

3. **Verwendung** (`app/services/db_service.py`)
   - `process_meeting_series_with_llm()` erstellt LLMService-Instanz
   - Ruft `llm_service.parse_meeting_series()` auf

4. **.env-Parameter** (bereits vorhanden)
   - `OPENAI_API_KEY=sk-proj-...`
   - `OPENAI_MODEL=gpt-5-nano`
   - `LLM_PROVIDER=openai`
   - Bestehende OLLAMA-Parameter: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`

## Ziel-Architektur

### Provider-Abstraktion

Die LLM-Provider-Integration soll über eine abstrakte Schnittstelle erfolgen, die es ermöglicht, verschiedene Provider zu unterstützen, ohne die Hauptlogik zu ändern.

```
LLMService
├── Provider-Abstraktion (Strategy Pattern)
│   ├── OllamaProvider
│   └── OpenAIProvider
└── Gemeinsame Logik (Prompt-Building, JSON-Parsing, Validierung)
```

## Implementierungsschritte

### Schritt 1: Erweiterung der Konfiguration (`app/config/database.py`)

**Ziel:** Neue Funktion `get_llm_config()` erstellen, die alle LLM-Parameter liest

**Änderungen:**
- Neue Funktion `get_llm_config(db_service: Optional[Any] = None) -> Dict[str, Any]`
- Liest `LLM_PROVIDER` aus .env (Standard: "ollama")
- Liest provider-spezifische Parameter:
  - Für OLLAMA: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_NUM_CTX`
  - Für OpenAI: `OPENAI_API_KEY`, `OPENAI_MODEL`
- Rückgabe-Format:
  ```python
  {
      "provider": "ollama" | "openai",
      "ollama": {
          "base_url": "...",
          "model": "...",
          "timeout": 30.0,
          "num_ctx": 4096
      },
      "openai": {
          "api_key": "...",
          "model": "..."
      }
  }
  ```
- Bestehende `get_ollama_config()` Funktion bleibt für Rückwärtskompatibilität erhalten

### Schritt 2: Provider-Abstraktion erstellen (`app/services/llm_providers/`)

**Ziel:** Neue Verzeichnisstruktur für Provider-Implementierungen

**Neue Dateien:**
- `app/services/llm_providers/__init__.py`
- `app/services/llm_providers/base_provider.py` (Abstrakte Basisklasse)
- `app/services/llm_providers/ollama_provider.py`
- `app/services/llm_providers/openai_provider.py`

**Abstrakte Basisklasse (`base_provider.py`):**
```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Ruft den LLM-Provider auf und gibt die Response zurück.
        
        Args:
            system_prompt: System-Prompt für das LLM
            user_prompt: User-Prompt mit den Eingabedaten
        
        Returns:
            Response-Text vom LLM
        """
        pass
    
    @abstractmethod
    async def check_availability(self) -> Tuple[bool, str]:
        """
        Prüft, ob der Provider erreichbar ist.
        
        Returns:
            Tuple (erfolgreich: bool, nachricht: str)
        """
        pass
```

**OllamaProvider (`ollama_provider.py`):**
- Implementiert `BaseLLMProvider`
- Enthält die aktuelle `_call_ollama()` Logik aus `LLMService`
- Konfiguration über Konstruktor-Parameter
- API-Endpoint: `{base_url}/api/generate`
- Request-Format: JSON mit `model`, `system`, `prompt`, `stream: false`, `format: "json"`

**OpenAIProvider (`openai_provider.py`):**
- Implementiert `BaseLLMProvider`
- Verwendet OpenAI Python SDK (`openai` Package) oder httpx für direkte API-Calls
- API-Endpoint: `https://api.openai.com/v1/chat/completions`
- Request-Format: JSON mit `model`, `messages` (system + user), `response_format: {"type": "json_object"}`
- Authentifizierung über `Authorization: Bearer {api_key}` Header
- Timeout-Konfiguration (Standard: 30 Sekunden, lesbar aus .env als `OPENAI_TIMEOUT`)

### Schritt 3: Refactoring von LLMService (`app/services/llm_service.py`)

**Ziel:** LLMService soll Provider-abstrakt arbeiten

**Änderungen:**
- Konstruktor erhält `provider: BaseLLMProvider` statt einzelner OLLAMA-Parameter
- Methode `_call_ollama()` wird entfernt
- Neue Methode `_call_llm()` verwendet `provider.generate()`
- Methode `check_availability()` verwendet `provider.check_availability()`
- Alle anderen Methoden bleiben unverändert:
  - `_build_system_prompt()` - unverändert
  - `_build_user_prompt()` - unverändert
  - `_parse_json_response()` - unverändert
  - `_validate_rrule_fields()` - unverändert
  - Alle `_convert_*()` Methoden - unverändert

**Neue Konstruktor-Signatur:**
```python
def __init__(self, provider: BaseLLMProvider):
    """
    Initialisiert den LLMService.
    
    Args:
        provider: LLM-Provider-Instanz (OllamaProvider oder OpenAIProvider)
    """
    self.provider = provider
    logger.info(f"LLMService initialisiert mit Provider: {type(provider).__name__}")
```

**Factory-Funktion für Provider-Erstellung:**
- Neue Funktion `create_llm_provider(config: Dict[str, Any]) -> BaseLLMProvider`
- Erstellt Provider-Instanz basierend auf `config["provider"]`
- Wird in `db_service.py` verwendet

### Schritt 4: Anpassung der Verwendung (`app/services/db_service.py`)

**Ziel:** Verwendung der neuen Konfiguration und Provider-Abstraktion

**Änderungen in `process_meeting_series_with_llm()`:**
- Import: `from app.config.database import get_llm_config`
- Import: `from app.services.llm_service import create_llm_provider, LLMService`
- Ersetze `get_ollama_config()` durch `get_llm_config()`
- Erstelle Provider mit `create_llm_provider(config)`
- Erstelle LLMService mit Provider: `LLMService(provider)`

**Änderungen in `_run_async_llm_processing()`:**
- Gleiche Anpassungen wie oben

### Schritt 5: Anpassung der Startup-Prüfung (`app/main.py`)

**Ziel:** Startup-Prüfung soll für beide Provider funktionieren

**Änderungen in `startup_event()`:**
- Import: `from app.config.database import get_llm_config`
- Import: `from app.services.llm_service import create_llm_provider, LLMService`
- Ersetze `get_ollama_config()` durch `get_llm_config()`
- Erstelle Provider und LLMService wie in `db_service.py`
- `check_availability()` funktioniert für beide Provider

### Schritt 6: Dependencies aktualisieren (`requirements.txt`)

**Ziel:** OpenAI SDK hinzufügen

**Änderungen:**
- Füge `openai>=1.0.0` hinzu (oder verwende httpx für direkte API-Calls)
- Falls httpx bereits vorhanden, kann es für beide Provider verwendet werden

## Technische Details

### OpenAI API-Request-Format

```python
{
    "model": "gpt-5-nano",
    "messages": [
        {
            "role": "system",
            "content": "<system_prompt>"
        },
        {
            "role": "user",
            "content": "<user_prompt>"
        }
    ],
    "response_format": {
        "type": "json_object"
    },
    "temperature": 0.0  # Für deterministische Ergebnisse
}
```

**Response-Format:**
```python
{
    "choices": [
        {
            "message": {
                "content": "<json_string>"
            }
        }
    ]
}
```

### Fehlerbehandlung

- Beide Provider sollten ähnliche Exception-Typen verwenden (httpx.TimeoutException, httpx.RequestError)
- Fehlerbehandlung in `LLMService.parse_meeting_series()` bleibt unverändert
- Provider-spezifische Fehler werden in den Provider-Klassen behandelt

### Timeout-Konfiguration

- OLLAMA: `OLLAMA_TIMEOUT` (bereits vorhanden)
- OpenAI: `OPENAI_TIMEOUT` (neu, Standard: 30.0)
- Beide Timeouts werden in den jeweiligen Provider-Klassen verwendet

## Rückwärtskompatibilität

- Bestehende `get_ollama_config()` Funktion bleibt erhalten
- Falls `LLM_PROVIDER` nicht gesetzt ist, Standard: "ollama"
- Bestehende OLLAMA-Parameter bleiben funktional
- Keine Breaking Changes für bestehenden Code

## Testing-Strategie

1. **Unit-Tests für Provider:**
   - Mock-Tests für `OllamaProvider.generate()`
   - Mock-Tests für `OpenAIProvider.generate()`
   - Verfügbarkeitsprüfungen

2. **Integration-Tests:**
   - End-to-End-Test mit OLLAMA
   - End-to-End-Test mit OpenAI
   - Provider-Wechsel zur Laufzeit

3. **Konfigurationstests:**
   - Fehlende Parameter
   - Ungültige Provider-Namen
   - Fallback-Verhalten

## Migration

### Schritt-für-Schritt

1. **Phase 1:** Provider-Abstraktion implementieren (OllamaProvider)
2. **Phase 2:** LLMService refactoren (Provider-Pattern)
3. **Phase 3:** OpenAIProvider implementieren
4. **Phase 4:** Konfiguration erweitern
5. **Phase 5:** Integration in db_service.py und main.py
6. **Phase 6:** Testing und Validierung

### Rollback-Plan

- Alle Änderungen sind rückwärtskompatibel
- Bei Problemen kann `LLM_PROVIDER=ollama` gesetzt werden
- Bestehende OLLAMA-Konfiguration bleibt funktional

## Dateien-Übersicht

### Zu erstellende Dateien:
- `app/services/llm_providers/__init__.py`
- `app/services/llm_providers/base_provider.py`
- `app/services/llm_providers/ollama_provider.py`
- `app/services/llm_providers/openai_provider.py`

### Zu ändernde Dateien:
- `app/config/database.py` - Neue Funktion `get_llm_config()`
- `app/services/llm_service.py` - Refactoring für Provider-Pattern
- `app/services/db_service.py` - Verwendung neuer Konfiguration
- `app/main.py` - Startup-Prüfung anpassen
- `requirements.txt` - OpenAI SDK hinzufügen

### Unveränderte Dateien:
- `app/config/llm_system_prompt.txt` - Bleibt identisch
- `app/services/calendar_series_service.py` - Keine Änderungen
- Alle anderen Service-Dateien

## Zusammenfassung

Die Implementierung erfolgt schrittweise mit klarer Trennung der Verantwortlichkeiten:

1. **Provider-Abstraktion:** Ermöglicht einfache Erweiterung um weitere Provider
2. **Konfiguration:** Zentrale Konfigurationsfunktion für alle LLM-Parameter
3. **Rückwärtskompatibilität:** Bestehender Code funktioniert weiterhin
4. **Testbarkeit:** Klare Schnittstellen ermöglichen einfaches Mocking

Die Lösung ist erweiterbar und wartbar, ohne die bestehende Funktionalität zu beeinträchtigen.
