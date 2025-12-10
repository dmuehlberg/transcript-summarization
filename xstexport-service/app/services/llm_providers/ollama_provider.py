"""
Ollama LLM Provider Implementierung.
"""

import logging
import httpx
from typing import Tuple, Optional

from app.services.llm_providers.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """
    Provider-Implementierung für Ollama.
    
    Verwendet die Ollama API zum Generieren von LLM-Responses.
    """
    
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 30.0,
        num_ctx: Optional[int] = None
    ):
        """
        Initialisiert den OllamaProvider.
        
        Args:
            base_url: Basis-URL des Ollama-Servers (z.B. "http://localhost:11434")
            model: Name des zu verwendenden Modells
            timeout: Timeout in Sekunden für LLM-Requests (Standard: 30.0)
            num_ctx: Größe des Kontextfensters (Tokens) für Ollama-Requests
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.num_ctx = num_ctx
        ctx_info = f", num_ctx: {self.num_ctx}" if self.num_ctx else ""
        logger.info(f"OllamaProvider initialisiert: base_url={self.base_url}, model={self.model}, timeout={self.timeout}s{ctx_info}")
    
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Ruft die Ollama API auf.
        
        Args:
            system_prompt: System-Prompt für das LLM
            user_prompt: User-Prompt mit den Eingabedaten
        
        Returns:
            Response-Text vom LLM
        """
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "format": "json"
        }
        if self.num_ctx:
            payload["options"] = {"num_ctx": self.num_ctx}
        
        # Erstelle explizites Timeout-Objekt für httpx
        timeout_obj = httpx.Timeout(self.timeout, connect=10.0)
        logger.debug(f"Ollama HTTP-Request mit Timeout: {self.timeout}s (connect: 10.0s)")
        
        async with httpx.AsyncClient(timeout=timeout_obj) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            # Ollama gibt die Antwort im "response" Feld zurück
            result = response.json()
            return result.get("response", "")
    
    async def check_availability(self) -> Tuple[bool, str]:
        """
        Prüft, ob Ollama erreichbar ist und das konfigurierte Modell verfügbar ist.
        
        Returns:
            Tuple (erfolgreich: bool, nachricht: str)
        """
        try:
            # Prüfe zuerst, ob Ollama erreichbar ist
            url = f"{self.base_url}/api/tags"
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                except httpx.RequestError as e:
                    return False, f"Ollama-Server nicht erreichbar unter {self.base_url}: {str(e)}"
                except httpx.HTTPStatusError as e:
                    return False, f"Ollama-Server antwortet mit Fehler {e.response.status_code}: {str(e)}"
                
                # Prüfe, ob das Modell verfügbar ist
                models_data = response.json()
                available_models = [model.get("name", "") for model in models_data.get("models", [])]
                
                if self.model not in available_models:
                    available_str = ", ".join(available_models[:5])  # Erste 5 Modelle anzeigen
                    if len(available_models) > 5:
                        available_str += f" ... (insgesamt {len(available_models)} Modelle)"
                    return False, f"Modell '{self.model}' nicht verfügbar. Verfügbare Modelle: {available_str if available_models else 'keine'}"
                
                return True, f"Ollama erreichbar und Modell '{self.model}' verfügbar"
                
        except Exception as e:
            return False, f"Unerwarteter Fehler bei Ollama-Prüfung: {str(e)}"
