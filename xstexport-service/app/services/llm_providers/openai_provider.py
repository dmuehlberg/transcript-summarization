"""
OpenAI LLM Provider Implementierung.
"""

import logging
import httpx
from typing import Tuple

from app.services.llm_providers.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    Provider-Implementierung für OpenAI.
    
    Verwendet die OpenAI Chat Completions API zum Generieren von LLM-Responses.
    """
    
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 30.0
    ):
        """
        Initialisiert den OpenAIProvider.
        
        Args:
            api_key: OpenAI API-Key
            model: Name des zu verwendenden Modells (z.B. "gpt-5-nano")
            timeout: Timeout in Sekunden für LLM-Requests (Standard: 30.0)
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = "https://api.openai.com/v1"
        logger.info(f"OpenAIProvider initialisiert: model={self.model}, timeout={self.timeout}s")
    
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
            ],
            "response_format": {
                "type": "json_object"
            },
            "temperature": 0.0  # Für deterministische Ergebnisse
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Erstelle explizites Timeout-Objekt für httpx
        timeout_obj = httpx.Timeout(self.timeout, connect=10.0)
        logger.debug(f"OpenAI HTTP-Request mit Timeout: {self.timeout}s (connect: 10.0s)")
        
        async with httpx.AsyncClient(timeout=timeout_obj) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            # OpenAI gibt die Antwort im choices[0].message.content Feld zurück
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                return content
            else:
                raise ValueError("OpenAI API Response enthält keine choices")
    
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
