"""
OpenAI LLM Provider Implementierung.
"""

import json
import logging
import httpx
from typing import Tuple, Dict, Any, Optional
from pathlib import Path

from app.services.llm_providers.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)

# Modelle, die Structured Outputs unterstützen
STRUCTURED_OUTPUTS_MODELS = [
    "gpt-4o-2024-08-06",
    "gpt-4o-mini-2024-07-18"
]


class OpenAIProvider(BaseLLMProvider):
    """
    Provider-Implementierung für OpenAI.
    
    Verwendet die OpenAI Chat Completions API zum Generieren von LLM-Responses.
    """
    
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        use_structured_outputs: bool = True
    ):
        """
        Initialisiert den OpenAIProvider.
        
        Args:
            api_key: OpenAI API-Key
            model: Name des zu verwendenden Modells (z.B. "gpt-4o-2024-08-06")
            timeout: Timeout in Sekunden für LLM-Requests (Standard: 30.0)
            use_structured_outputs: Ob Structured Outputs verwendet werden sollen (Standard: True)
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = "https://api.openai.com/v1"
        self.use_structured_outputs = use_structured_outputs
        
        # Prüfe, ob Modell Structured Outputs unterstützt
        self.supports_structured_outputs = self._model_supports_structured_outputs(model)
        
        # Lade JSON Schema, falls Structured Outputs verwendet werden sollen
        self.json_schema = None
        if self.use_structured_outputs and self.supports_structured_outputs:
            try:
                self.json_schema = self._load_json_schema()
                logger.info(f"OpenAIProvider initialisiert: model={self.model}, timeout={self.timeout}s, Structured Outputs aktiviert")
            except Exception as e:
                logger.warning(f"Konnte JSON Schema nicht laden, verwende Fallback auf json_object: {str(e)}")
                self.use_structured_outputs = False
        elif self.use_structured_outputs and not self.supports_structured_outputs:
            logger.warning(f"Modell '{self.model}' unterstützt keine Structured Outputs, verwende Fallback auf json_object")
            self.use_structured_outputs = False
        
        if not self.use_structured_outputs:
            logger.info(f"OpenAIProvider initialisiert: model={self.model}, timeout={self.timeout}s, json_object Modus")
    
    def _model_supports_structured_outputs(self, model: str) -> bool:
        """
        Prüft, ob das Modell Structured Outputs unterstützt.
        
        Args:
            model: Modell-Name
        
        Returns:
            True wenn unterstützt, False sonst
        """
        # Prüfe exakte Übereinstimmung oder Präfix
        for supported_model in STRUCTURED_OUTPUTS_MODELS:
            if model == supported_model or model.startswith(supported_model.split("-")[0] + "-" + supported_model.split("-")[1]):
                # Prüfe, ob es eine spezifische Version ist (mit Datum)
                if "-2024-" in model or model == supported_model:
                    return True
        return False
    
    def _load_json_schema(self) -> Dict[str, Any]:
        """
        Lädt das JSON Schema aus der Konfigurationsdatei.
        
        Returns:
            Dictionary mit JSON Schema
        
        Raises:
            FileNotFoundError: Wenn Schema-Datei nicht gefunden wird
            json.JSONDecodeError: Wenn Schema-Datei ungültiges JSON enthält
        """
        # Pfad zur Schema-Datei relativ zum aktuellen Modul
        current_dir = Path(__file__).parent.parent.parent  # app/services/llm_providers -> app
        schema_file = current_dir / "config" / "llm_response_schema.json"
        
        try:
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema = json.load(f)
                logger.debug(f"JSON Schema erfolgreich geladen aus {schema_file}")
                return schema
        except FileNotFoundError:
            logger.error(f"JSON Schema-Datei nicht gefunden: {schema_file}")
            raise FileNotFoundError(
                f"JSON Schema-Datei nicht gefunden: {schema_file}. "
                "Bitte erstellen Sie die Datei app/config/llm_response_schema.json"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Fehler beim Parsen der JSON Schema-Datei: {str(e)}")
            raise
    
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Ruft die OpenAI Chat Completions API auf.
        
        Args:
            system_prompt: System-Prompt für das LLM
            user_prompt: User-Prompt mit den Eingabedaten
        
        Returns:
            Response-Text vom LLM (JSON-String)
        """
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
            # temperature wird weggelassen, da einige Modelle nur den Default-Wert (1) unterstützen
            # Für deterministische Ergebnisse sollte das System-Prompt ausreichend sein
        }
        
        # Verwende Structured Outputs, falls aktiviert und unterstützt
        if self.use_structured_outputs and self.json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "strict": True,
                    "schema": self.json_schema
                }
            }
            logger.debug("Verwende Structured Outputs mit JSON Schema")
        else:
            payload["response_format"] = {
                "type": "json_object"
            }
            logger.debug("Verwende json_object Modus (Fallback)")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Erstelle explizites Timeout-Objekt für httpx
        timeout_obj = httpx.Timeout(self.timeout, connect=10.0)
        logger.debug(f"OpenAI HTTP-Request mit Timeout: {self.timeout}s (connect: 10.0s)")
        
        async with httpx.AsyncClient(timeout=timeout_obj) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                # OpenAI gibt die Antwort im choices[0].message.content Feld zurück
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0].get("message", {}).get("content", "")
                    return content
                else:
                    raise ValueError("OpenAI API Response enthält keine choices")
            except httpx.HTTPStatusError as e:
                # Detaillierte Fehlermeldung aus Response-Body extrahieren
                error_detail = str(e)
                try:
                    error_response = e.response.json()
                    if "error" in error_response:
                        error_info = error_response["error"]
                        error_message = error_info.get("message", str(e))
                        error_type = error_info.get("type", "unknown")
                        error_detail = f"{error_type}: {error_message}"
                        logger.error(f"OpenAI API Fehler: {error_detail}")
                except (json.JSONDecodeError, KeyError):
                    # Falls Parsing fehlschlägt, verwende Standard-Fehlermeldung
                    logger.error(f"OpenAI API Fehler (Status {e.response.status_code}): {str(e)}")
                raise Exception(f"OpenAI API Fehler: {error_detail}") from e
    
    async def check_availability(self) -> Tuple[bool, str]:
        """
        Prüft, ob OpenAI erreichbar ist und der API-Key gültig ist.
        
        Returns:
            Tuple (erfolgreich: bool, nachricht: str)
        """
        try:
            # Prüfe durch einen einfachen API-Call (Models-Liste)
            url = f"{self.base_url}/models"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    
                    # Prüfe, ob das Modell verfügbar ist (optional)
                    models_data = response.json()
                    available_models = [model.get("id", "") for model in models_data.get("data", [])]
                    
                    # Modell-Name könnte mit Präfix kommen (z.B. "gpt-5-nano" vs "gpt-5-nano-2024-...")
                    model_available = any(
                        self.model in model_id or model_id.startswith(self.model)
                        for model_id in available_models
                    )
                    
                    if not model_available:
                        # Warnung, aber nicht als Fehler behandeln (Modelle können sich ändern)
                        logger.warning(f"Modell '{self.model}' möglicherweise nicht in verfügbaren Modellen gefunden")
                    
                    return True, f"OpenAI API erreichbar und API-Key gültig (Modell: {self.model})"
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        return False, f"OpenAI API-Key ungültig oder nicht autorisiert (Status: 401)"
                    elif e.response.status_code == 429:
                        return False, f"OpenAI API Rate Limit erreicht (Status: 429)"
                    else:
                        return False, f"OpenAI API antwortet mit Fehler {e.response.status_code}: {str(e)}"
                except httpx.RequestError as e:
                    return False, f"OpenAI API nicht erreichbar: {str(e)}"
                
        except Exception as e:
            return False, f"Unerwarteter Fehler bei OpenAI-Prüfung: {str(e)}"
